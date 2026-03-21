import { initializeApp } from 'firebase/app'
import { getAuth } from 'firebase/auth'
import { getFirestore } from 'firebase/firestore'

const firebaseEnv = {
  VITE_FIREBASE_API_KEY: import.meta.env.VITE_FIREBASE_API_KEY,
  VITE_FIREBASE_AUTH_DOMAIN: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  VITE_FIREBASE_PROJECT_ID: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  VITE_FIREBASE_STORAGE_BUCKET: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
  VITE_FIREBASE_MESSAGING_SENDER_ID: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  VITE_FIREBASE_APP_ID: import.meta.env.VITE_FIREBASE_APP_ID,
}

console.log('Firebase ENV:', import.meta.env)
console.log('Firebase config values:', firebaseEnv)

const missingFirebaseVars = Object.entries(firebaseEnv)
  .filter(([, value]) => !value)
  .map(([key]) => key)

const firebaseEnvError = missingFirebaseVars.length
  ? `Missing Firebase environment variables: ${missingFirebaseVars.join(', ')}`
  : ''

const firebaseConfig = {
  apiKey: firebaseEnv.VITE_FIREBASE_API_KEY,
  authDomain: firebaseEnv.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: firebaseEnv.VITE_FIREBASE_PROJECT_ID,
  storageBucket: firebaseEnv.VITE_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: firebaseEnv.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId: firebaseEnv.VITE_FIREBASE_APP_ID,
}

const hasFirebaseConfig = !missingFirebaseVars.length

let app = null
let auth = null
let db = null

if (hasFirebaseConfig) {
  app = initializeApp(firebaseConfig)
  auth = getAuth(app)
  db = getFirestore(app)
} else {
  console.error(firebaseEnvError)
}

export { app, auth, db, firebaseConfig, firebaseEnv, firebaseEnvError, hasFirebaseConfig, missingFirebaseVars }
