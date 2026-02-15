from __future__ import annotations

import json
import logging
from typing import Callable

from PyQt6.QtCore import QObject, QUrl, pyqtSignal, pyqtSlot
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtWebEngineWidgets import QWebEngineView


HOOK_JS = """
(function() {
  if (window.__quotexHookInstalled) return;
  window.__quotexHookInstalled = true;

  function emit(payload) {
    if (window.pyBridge && window.pyBridge.onData) {
      window.pyBridge.onData(JSON.stringify(payload));
    }
  }

  const NativeWS = window.WebSocket;
  window.WebSocket = function(url, protocols) {
    const ws = protocols ? new NativeWS(url, protocols) : new NativeWS(url);
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

  setInterval(function() {
    try {
      const chartStore = window.store || window.__NUXT__ || window.App;
      if (!chartStore) return;
      emit({type: 'state_probe', payload: chartStore, ts: Date.now()});
    } catch (e) {}
  }, 1000);
})();
"""


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

    def __init__(self, quotex_url: str) -> None:
        super().__init__()
        self.logger = logging.getLogger(self.__class__.__name__)
        self.view = QWebEngineView()
        self.view.setWindowTitle("Quotex Embedded Browser")
        self.view.resize(1280, 820)
        self.view.load(QUrl(quotex_url))

        self.bridge = BrowserBridge()
        self.channel = QWebChannel(self.view.page())
        self.channel.registerObject("pyBridge", self.bridge)
        self.view.page().setWebChannel(self.channel)
        self.view.loadFinished.connect(self._on_loaded)

    def _on_loaded(self, ok: bool) -> None:
        if not ok:
            self.logger.error("Failed to load Quotex page")
            return
        init_bridge = """
            if (typeof qt !== 'undefined') {
              new QWebChannel(qt.webChannelTransport, function(channel) {
                window.pyBridge = channel.objects.pyBridge;
              });
            }
        """
        self.view.page().runJavaScript(init_bridge)
        self.view.page().runJavaScript(HOOK_JS)
        self.page_loaded.emit()

    def show(self) -> None:
        self.view.show()

    def evaluate_js(self, script: str, callback: Callable | None = None) -> None:
        self.view.page().runJavaScript(script, callback if callback else (lambda _: None))

    def reload(self) -> None:
        self.view.reload()
