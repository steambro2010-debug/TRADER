import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import {
  GoogleAuthProvider,
  browserLocalPersistence,
  onAuthStateChanged,
  setPersistence,
  signInWithPopup,
  signOut,
} from 'firebase/auth'
import {
  collection,
  doc,
  onSnapshot,
  serverTimestamp,
  setDoc,
} from 'firebase/firestore'
import { auth, db, hasFirebaseConfig } from '../lib/firebase'
import {
  TODAY_LOG_KEY,
  buildWeightMetrics,
  defaultDailyLog,
  defaultProfile,
  normalizeDailyLog,
  normalizeProfile,
} from '../lib/tracker'

const PROGRESS_PHOTO_STORAGE_KEY = 'cut-tracker-progress-photo'
const AppContext = createContext(null)

function readProgressPhoto() {
  if (typeof window === 'undefined') return ''
  try {
    return window.localStorage.getItem(PROGRESS_PHOTO_STORAGE_KEY) ?? ''
  } catch {
    return ''
  }
}

export function AppProvider({ children }) {
  const [authReady, setAuthReady] = useState(!hasFirebaseConfig)
  const [user, setUser] = useState(null)
  const [profile, setProfile] = useState(defaultProfile)
  const [checkins, setCheckins] = useState({})
  const [loadingData, setLoadingData] = useState(false)
  const [errorMessage, setErrorMessage] = useState('')
  const [progressPhoto, setProgressPhoto] = useState(readProgressPhoto)

  useEffect(() => {
    if (typeof window === 'undefined') return undefined
    try {
      window.localStorage.setItem(PROGRESS_PHOTO_STORAGE_KEY, progressPhoto)
    } catch {}
    return undefined
  }, [progressPhoto])

  useEffect(() => {
    if (!hasFirebaseConfig || !auth) return undefined

    setPersistence(auth, browserLocalPersistence).catch(() => {
      setErrorMessage('Could not persist your session. You can still try signing in again.')
    })

    const unsubscribe = onAuthStateChanged(auth, (nextUser) => {
      setUser(nextUser)
      setAuthReady(true)
      setErrorMessage('')
      if (!nextUser) {
        setProfile(defaultProfile)
        setCheckins({})
      }
    })

    return unsubscribe
  }, [])

  useEffect(() => {
    if (!user || !db) return undefined

    setLoadingData(true)
    const userRef = doc(db, 'users', user.uid)
    const checkinsRef = collection(db, 'users', user.uid, 'checkins')

    const unsubscribeUser = onSnapshot(userRef, (snapshot) => {
      const data = snapshot.data()
      setProfile(normalizeProfile(data?.profile ?? defaultProfile))
      setLoadingData(false)
    }, () => {
      setErrorMessage('Could not load your profile data. Please refresh and try again.')
      setLoadingData(false)
    })

    const unsubscribeCheckins = onSnapshot(checkinsRef, (snapshot) => {
      const nextCheckins = {}
      snapshot.forEach((entry) => {
        nextCheckins[entry.id] = normalizeDailyLog(entry.data(), entry.id)
      })
      setCheckins(nextCheckins)
      setLoadingData(false)
    }, () => {
      setErrorMessage('Could not load your check-ins. Please refresh and try again.')
      setLoadingData(false)
    })

    return () => {
      unsubscribeUser()
      unsubscribeCheckins()
    }
  }, [user])

  async function signInWithGoogle() {
    if (!hasFirebaseConfig || !auth) {
      setErrorMessage('Firebase is not configured yet. Add Vite Firebase environment variables to enable login.')
      return false
    }

    try {
      setErrorMessage('')
      const provider = new GoogleAuthProvider()
      await signInWithPopup(auth, provider)
      return true
    } catch {
      setErrorMessage('Google sign-in failed. Please try again.')
      return false
    }
  }

  async function signOutUser() {
    if (!auth) return
    try {
      await signOut(auth)
    } catch {
      setErrorMessage('Logout failed. Please try again.')
    }
  }

  async function saveProfile(nextProfile) {
    if (!user || !db) return false
    const normalized = normalizeProfile(nextProfile)

    try {
      setErrorMessage('')
      await setDoc(doc(db, 'users', user.uid), {
        profile: normalized,
        updatedAt: serverTimestamp(),
      }, { merge: true })
      return true
    } catch {
      setErrorMessage('Could not save your profile. Please try again.')
      return false
    }
  }

  async function saveDailyLog(nextLog) {
    if (!user || !db) return false
    const dateKey = nextLog?.date || TODAY_LOG_KEY
    if (checkins[dateKey]) {
      setErrorMessage('A check-in already exists for today. Duplicate entries are disabled.')
      return false
    }

    const normalized = normalizeDailyLog({ ...defaultDailyLog, ...nextLog }, dateKey)
    const nextCheckins = { ...checkins, [dateKey]: normalized }
    const streakData = buildWeightMetrics(nextCheckins)

    try {
      setErrorMessage('')
      await setDoc(doc(db, 'users', user.uid, 'checkins', dateKey), {
        ...normalized,
        updatedAt: serverTimestamp(),
      })
      await setDoc(doc(db, 'users', user.uid), {
        streakData: {
          streakCount: streakData.streakCount,
          latestWeight: streakData.latestWeight,
          sevenDayStatus: streakData.sevenDayStatus,
        },
        updatedAt: serverTimestamp(),
      }, { merge: true })
      return true
    } catch {
      setErrorMessage('Could not save today’s check-in. Please try again.')
      return false
    }
  }

  function saveProgressPhoto(file) {
    if (!file) return
    const reader = new FileReader()
    reader.onload = () => {
      if (typeof reader.result === 'string') {
        setProgressPhoto(reader.result)
      }
    }
    reader.readAsDataURL(file)
  }

  const value = useMemo(() => ({
    authReady,
    user,
    profile,
    checkins,
    loadingData,
    errorMessage,
    hasFirebaseConfig,
    progressPhoto,
    saveProgressPhoto,
    signInWithGoogle,
    signOutUser,
    saveProfile,
    saveDailyLog,
  }), [authReady, user, profile, checkins, loadingData, errorMessage, progressPhoto])

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>
}

export function useAppContext() {
  const context = useContext(AppContext)
  if (!context) throw new Error('useAppContext must be used within AppProvider')
  return context
}
