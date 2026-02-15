from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Callable

from PyQt6.QtCore import QObject, Qt, QTimer, QUrl, pyqtSignal, pyqtSlot
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineSettings
from PyQt6.QtWebEngineWidgets import QWebEngineView


HOOK_JS = """
(function() {
  if (window.__quotexHookInstalled) return 'already_installed';
  if (!window.pyBridge || !window.pyBridge.onData) return 'bridge_not_ready';
  window.__quotexHookInstalled = true;

  function emit(payload) {
    try {
      window.pyBridge.onData(JSON.stringify(payload));
    } catch (e) {}
  }

  const NativeWS = window.WebSocket;
  window.WebSocket = function(url, protocols) {
    const ws = protocols ? new NativeWS(url, protocols) : new NativeWS(url);
    ws.addEventListener('open', function() {
      emit({type: 'ws_open', url: ws.url, ts: Date.now()});
    });
    ws.addEventListener('close', function() {
      emit({type: 'ws_close', url: ws.url, ts: Date.now()});
    });
    ws.addEventListener('error', function() {
      emit({type: 'ws_error', url: ws.url, ts: Date.now()});
    });
    ws.addEventListener('message', function(event) {
      try {
        const msg = typeof event.data === 'string' ? JSON.parse(event.data) : event.data;
        emit({type: 'ws_message', url: ws.url, payload: msg, ts: Date.now()});
      } catch (e) {
        emit({type: 'ws_raw', url: ws.url, payload: String(event.data), ts: Date.now()});
      }
    });

    const nativeSend = ws.send.bind(ws);
    ws.send = function(data) {
      try {
        const parsed = typeof data === 'string' ? JSON.parse(data) : data;
        emit({type: 'ws_send', url: ws.url, payload: parsed, ts: Date.now()});
      } catch (e) {
        emit({type: 'ws_send_raw', url: ws.url, payload: String(data), ts: Date.now()});
      }
      return nativeSend(data);
    };
    return ws;
  };
  window.WebSocket.prototype = NativeWS.prototype;

  emit({type: 'hook_ready', ts: Date.now()});
  return 'hook_installed';
})();
"""


class LoggingWebEnginePage(QWebEnginePage):
    def javaScriptConsoleMessage(self, level, message, line_number, source_id):  # type: ignore[override]
        logger = logging.getLogger(self.__class__.__name__)
        logger.info("JS console [%s] %s:%s %s", level, source_id, line_number, message)


class BrowserBridge(QObject):
    packet_received = pyqtSignal(dict)

    @pyqtSlot(str)
    def onData(self, message: str) -> None:
        try:
            payload = json.loads(message)
            self.packet_received.emit(payload)
        except Exception:
            logging.getLogger(self.__class__.__name__).debug("Non-JSON bridge message: %s", message)


class QuotexBrowserEngine(QObject):
    page_loaded = pyqtSignal()
    hook_installed = pyqtSignal(bool)

    def __init__(self, quotex_url: str, profile_path: str, cache_path: str, user_agent: str, injection_delay_ms: int) -> None:
        super().__init__()
        self.logger = logging.getLogger(self.__class__.__name__)
        self.injection_delay_ms = injection_delay_ms
        self.hook_is_active = False

        profile_dir = Path(profile_path)
        cache_dir = Path(cache_path)
        profile_dir.mkdir(parents=True, exist_ok=True)
        cache_dir.mkdir(parents=True, exist_ok=True)

        self.profile = QWebEngineProfile("quotex-profile", self)
        self.profile.setPersistentStoragePath(str(profile_dir.resolve()))
        self.profile.setCachePath(str(cache_dir.resolve()))
        self.profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies)
        self.profile.setHttpUserAgent(user_agent)

        self.view = QWebEngineView()
        self.view.setWindowTitle("Quotex Embedded Browser")
        self.view.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        page = LoggingWebEnginePage(self.profile, self.view)
        self.view.setPage(page)
        settings = page.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.WebGLEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.Accelerated2dCanvasEnabled, True)

        self.bridge = BrowserBridge()
        self.bridge.packet_received.connect(self._on_bridge_packet)
        self.channel = QWebChannel(page)
        self.channel.registerObject("pyBridge", self.bridge)
        page.setWebChannel(self.channel)

        self.view.loadFinished.connect(self._on_loaded)
        self.view.load(QUrl(quotex_url))

    def _on_bridge_packet(self, packet: dict) -> None:
        if packet.get("type") == "hook_ready":
            self.hook_is_active = True
            self.hook_installed.emit(True)

    def _on_loaded(self, ok: bool) -> None:
        if not ok:
            self.logger.error("Failed to load Quotex page")
            self.hook_installed.emit(False)
            return

        init_bridge = """
            if (typeof qt !== 'undefined') {
              new QWebChannel(qt.webChannelTransport, function(channel) {
                window.pyBridge = channel.objects.pyBridge;
              });
            }
        """
        self.view.page().runJavaScript(init_bridge)

        def delayed_inject() -> None:
            self.view.page().runJavaScript(HOOK_JS, self._handle_injection_result)

        QTimer.singleShot(self.injection_delay_ms, delayed_inject)

        self.view.setFocus(Qt.FocusReason.ActiveWindowFocusReason)
        self.view.activateWindow()
        QTimer.singleShot(50, lambda: self.view.setFocus(Qt.FocusReason.TabFocusReason))
        self.page_loaded.emit()

    def _handle_injection_result(self, result) -> None:
        ok = result in {"hook_installed", "already_installed"}
        self.logger.info("Hook injection result: %s", result)
        self.hook_is_active = ok
        self.hook_installed.emit(ok)

    def evaluate_js(self, script: str, callback: Callable | None = None) -> None:
        self.view.page().runJavaScript(script, callback if callback else (lambda _: None))

    def reload(self) -> None:
        self.hook_is_active = False
        self.view.reload()
