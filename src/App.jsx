import { useEffect, useMemo, useState } from 'react'
import { NavLink, Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { useAppContext } from './context/AppContext'
import {
  TODAY_LOG_KEY,
  buildAlerts,
  buildCoachInsights,
  buildWeightMetrics,
  buildWeeklySummary,
  buildWorkoutTemplate,
  defaultDailyLog,
  getCompletedExerciseCount,
  normalizeDailyLog,
  normalizeProfile,
} from './lib/tracker'

const tabs = [
  { name: 'Dashboard', path: '/dashboard', eyebrow: 'Overview', title: 'Premium progress tracking', description: 'Weight, streaks, coaching, and quick actions in one clean dashboard.' },
  { name: 'Check-in', path: '/check-in', eyebrow: 'Daily log', title: 'Today’s training checklist', description: 'Log weight, diet, and each exercise with a clean card-based flow.' },
  { name: 'Plan', path: '/plan', eyebrow: 'Workout plan', title: 'Adaptive plan for today', description: 'Today’s training adjusts from your profile and recent workout performance.' },
  { name: 'Coach', path: '/coach', eyebrow: 'Coach', title: 'Rule-based direction', description: 'Simple coaching that reacts to your streak, adherence, and weight trend.' },
]

function App() {
  const {
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
  } = useAppContext()

  const normalizedProfile = useMemo(() => normalizeProfile(profile), [profile])
  const normalizedCheckins = useMemo(
    () => Object.fromEntries(Object.entries(checkins).map(([dateKey, log]) => [dateKey, normalizeDailyLog(log, dateKey)])),
    [checkins],
  )
  const hasProfile = Boolean(normalizedProfile.age && normalizedProfile.height && normalizedProfile.weight && normalizedProfile.fitnessLevel)

  if (!authReady) {
    return <FullPageMessage title="Preparing your workspace" message="Checking your saved session and loading your tracker." />
  }

  if (!user) {
    return <AuthScreen hasFirebaseConfig={hasFirebaseConfig} errorMessage={errorMessage} onLogin={signInWithGoogle} />
  }

  return (
    <AppShell user={user} profile={normalizedProfile} onLogout={signOutUser} errorMessage={errorMessage}>
      {loadingData ? <InlineBanner tone="info" title="Syncing" message="Loading your profile and check-ins from Firestore." /> : null}
      <AnimatedRoutes
        profile={normalizedProfile}
        hasProfile={hasProfile}
        dailyLogs={normalizedCheckins}
        progressPhoto={progressPhoto}
        onPhotoUpload={saveProgressPhoto}
        onSaveProfile={saveProfile}
        onSaveDailyLog={saveDailyLog}
      />
    </AppShell>
  )
}

function FullPageMessage({ title, message }) {
  return (
    <div className="app-frame min-h-screen px-4 py-10">
      <div className="mx-auto flex min-h-[60vh] max-w-md items-center justify-center">
        <Card className="w-full p-6 text-center">
          <p className="eyebrow">30 Day Cut Tracker</p>
          <h1 className="section-title mt-3">{title}</h1>
          <p className="section-copy mt-3">{message}</p>
        </Card>
      </div>
    </div>
  )
}

function AuthScreen({ hasFirebaseConfig, errorMessage, onLogin }) {
  return (
    <div className="app-frame min-h-screen px-4 py-8">
      <div className="mx-auto flex min-h-screen max-w-md items-center">
        <div className="w-full space-y-5">
          <Card className="p-6">
            <div className="badge-row mb-5 inline-flex">Install-ready PWA</div>
            <h1 className="text-3xl font-semibold tracking-tight text-white">Track your cut with synced progress.</h1>
            <p className="section-copy mt-4">
              Sign in with Google to save your profile, check-ins, workout progress, and streak data to Firestore.
            </p>
            <div className="mt-6 space-y-3">
              {[
                'Google login with persistent session',
                'Firestore sync across devices',
                'Mobile-first dashboard and daily checklist',
              ].map((item) => (
                <div key={item} className="list-row">
                  <span className="status-dot" />
                  <span>{item}</span>
                </div>
              ))}
            </div>
          </Card>

          {!hasFirebaseConfig ? (
            <InlineBanner tone="warning" title="Firebase setup required" message="Add VITE_FIREBASE_* environment variables before enabling Google login." />
          ) : null}
          {errorMessage ? <InlineBanner tone="danger" title="Sign-in issue" message={errorMessage} /> : null}

          <button type="button" onClick={onLogin} disabled={!hasFirebaseConfig} className="primary-button w-full">
            Continue with Google
          </button>
        </div>
      </div>
    </div>
  )
}

function AppShell({ user, profile, onLogout, errorMessage, children }) {
  const location = useLocation()
  const isOnboarding = location.pathname === '/onboarding'
  const activeTab = tabs.find((tab) => location.pathname.startsWith(tab.path)) ?? tabs[0]

  return (
    <div className="app-frame min-h-screen px-4 py-5 sm:px-6">
      <div className="mx-auto flex min-h-screen w-full max-w-md flex-col gap-4">
        <Card className="hero-card p-5 sm:p-6">
          <div className="flex items-start justify-between gap-4">
            <div className="space-y-3">
              <div>
                <p className="eyebrow">30 Day Cut Tracker</p>
                <h1 className="text-[1.8rem] font-semibold tracking-tight text-white">{activeTab.name}</h1>
              </div>
              <p className="section-copy max-w-[24rem]">{activeTab.description}</p>
            </div>
            <button type="button" onClick={onLogout} className="secondary-button shrink-0">
              Logout
            </button>
          </div>
          <div className="mt-5 grid grid-cols-2 gap-3">
            <StatTile label="Signed in as" value={user.displayName || user.email || 'Google user'} tone="primary" />
            <StatTile label="Profile weight" value={`${profile.weight || '--'} kg`} tone="neutral" />
          </div>
          {errorMessage && !isOnboarding ? <div className="mt-4"><InlineBanner tone="danger" title="Sync issue" message={errorMessage} /></div> : null}
        </Card>

        <div className="flex-1 space-y-4">{children}</div>

        {!isOnboarding ? <BottomNav /> : null}
      </div>
    </div>
  )
}

function AnimatedRoutes({ profile, hasProfile, dailyLogs, progressPhoto, onPhotoUpload, onSaveProfile, onSaveDailyLog }) {
  const location = useLocation()
  const metrics = useMemo(() => buildWeightMetrics(dailyLogs), [dailyLogs])
  const alerts = useMemo(() => buildAlerts(dailyLogs, metrics), [dailyLogs, metrics])
  const weeklySummary = useMemo(() => buildWeeklySummary(dailyLogs), [dailyLogs])
  const coachInsights = useMemo(() => buildCoachInsights(profile, dailyLogs, metrics), [profile, dailyLogs, metrics])
  const recentLogs = useMemo(
    () => Object.entries(dailyLogs).map(([dateKey, log]) => normalizeDailyLog(log, dateKey)).sort((a, b) => a.date.localeCompare(b.date)).slice(-7),
    [dailyLogs],
  )
  const workoutPlan = useMemo(() => buildWorkoutTemplate(profile, recentLogs, metrics), [profile, recentLogs, metrics])
  const hasLogToday = Boolean(dailyLogs[TODAY_LOG_KEY])
  const totalLogs = Object.keys(dailyLogs).length
  const todayLog = normalizeDailyLog(dailyLogs[TODAY_LOG_KEY] ?? defaultDailyLog, TODAY_LOG_KEY)

  return (
    <main key={location.pathname} className="page-transition flex-1 pb-24">
      <Routes location={location}>
        <Route path="/" element={<Navigate to={hasProfile ? '/dashboard' : '/onboarding'} replace />} />
        <Route path="/onboarding" element={<OnboardingPage initialProfile={profile} onSave={onSaveProfile} />} />
        <Route path="/dashboard" element={hasProfile ? <DashboardPage profile={profile} metrics={metrics} alerts={alerts} weeklySummary={weeklySummary} coachInsights={coachInsights} progressPhoto={progressPhoto} onPhotoUpload={onPhotoUpload} /> : <Navigate to="/onboarding" replace />} />
        <Route path="/check-in" element={hasProfile ? <CheckInPage currentLog={todayLog} hasLogToday={hasLogToday} onSaveLog={onSaveDailyLog} savedCount={totalLogs} workoutPlan={workoutPlan} /> : <Navigate to="/onboarding" replace />} />
        <Route path="/plan" element={hasProfile ? <PlanPage coachInsights={coachInsights} /> : <Navigate to="/onboarding" replace />} />
        <Route path="/coach" element={hasProfile ? <CoachPage coachInsights={coachInsights} /> : <Navigate to="/onboarding" replace />} />
      </Routes>
    </main>
  )
}

function DashboardPage({ profile, metrics, alerts, weeklySummary, coachInsights, progressPhoto, onPhotoUpload }) {
  return (
    <div className="page-stack">
      {alerts.length ? alerts.map((alert) => <InlineBanner key={alert.title} tone={alert.type === 'warning' ? 'warning' : 'danger'} title={alert.title} message={alert.message} />) : null}

      <div className="grid gap-4 sm:grid-cols-2">
        <Card className="p-5">
          <SectionHeading eyebrow="Weight" title="Current weight" description="Live from your synced check-ins." />
          <div className="mt-4 space-y-3">
            <p className="metric-hero">{metrics.latestWeight}</p>
            <div className="flex items-center justify-between text-sm text-slate-300">
              <span>Trend</span>
              <span className="font-medium text-white">{metrics.trendLabel}</span>
            </div>
            <div className="flex items-center justify-between text-sm text-slate-300">
              <span>Total lost</span>
              <span className="font-medium text-white">{metrics.totalWeightLost}</span>
            </div>
          </div>
        </Card>

        <Card className="p-5">
          <SectionHeading eyebrow="Streak" title="Consistency" description="Your most recent logging rhythm." />
          <div className="mt-4 space-y-4">
            <p className="metric-hero">{metrics.streakCount} days</p>
            <div className="rounded-2xl border border-white/10 bg-white/5 p-4 text-sm text-slate-300">
              <div className="flex items-center justify-between gap-3">
                <span>7-day status</span>
                <span className="rounded-full border border-cyan-400/30 bg-cyan-400/10 px-3 py-1 text-xs font-semibold text-cyan-100">{metrics.sevenDayStatus}</span>
              </div>
              <div className="mt-4 h-2 overflow-hidden rounded-full bg-white/10">
                <div className="h-full rounded-full bg-gradient-to-r from-cyan-400 to-emerald-400" style={{ width: `${metrics.progressPercent}%` }} />
              </div>
              <p className="mt-3 text-xs text-slate-400">Estimated fat loss progress: {metrics.estimatedFatLossPercent}</p>
            </div>
          </div>
        </Card>
      </div>

      <Card className="p-5">
        <SectionHeading eyebrow="Graph" title="Weight trend" description="Each point comes from a saved Firestore check-in." />
        <div className="mt-4"><WeightTrendChart chartData={metrics.chartData} /></div>
      </Card>

      <Card className="p-5">
        <SectionHeading eyebrow="Coach message" title={coachInsights.adviceMessage} description="Clear direction based on your recent adherence and progress." />
        <div className="mt-4 grid gap-3">
          <div className="rounded-2xl border border-cyan-400/20 bg-cyan-400/10 p-4 text-sm text-cyan-50 whitespace-pre-line">{coachInsights.readablePlan}</div>
          <div className="grid gap-3 sm:grid-cols-3">
            <StatTile label="Check-ins" value={String(weeklySummary.checkIns)} tone="neutral" />
            <StatTile label="Workouts" value={String(weeklySummary.workoutsCompleted)} tone="neutral" />
            <StatTile label="Diet hits" value={String(weeklySummary.dietHits)} tone="neutral" />
          </div>
        </div>
      </Card>

      <Card className="p-5">
        <SectionHeading eyebrow="Profile" title="Your stored baseline" description="This profile now syncs through Firebase Auth + Firestore." />
        <div className="mt-4 grid grid-cols-2 gap-3">
          <StatTile label="Age" value={profile.age || '--'} tone="neutral" />
          <StatTile label="Height" value={`${profile.height || '--'} cm`} tone="neutral" />
          <StatTile label="Weight" value={`${profile.weight || '--'} kg`} tone="neutral" />
          <StatTile label="Level" value={profile.fitnessLevel} tone="neutral" />
        </div>
      </Card>

      <Card className="p-5">
        <SectionHeading eyebrow="Progress photo" title="Visual reference" description="Kept locally on this device so your visual check-in stays quick and private." />
        <div className="mt-4 space-y-4">
          <label className="upload-zone">
            <span className="text-sm font-medium text-white">Choose a photo</span>
            <span className="text-xs text-slate-400">Optional visual check-in</span>
            <input type="file" accept="image/*" onChange={(event) => onPhotoUpload(event.target.files?.[0])} className="mt-3 block w-full text-xs text-slate-400" />
          </label>
          {progressPhoto ? <img src={progressPhoto} alt="Progress upload" className="h-56 w-full rounded-3xl object-cover" /> : <EmptyState title="No photo yet" message="Upload a photo to keep a visual reference on this device." />}
        </div>
      </Card>
    </div>
  )
}

function CheckInPage({ currentLog, hasLogToday, onSaveLog, savedCount, workoutPlan }) {
  const [formData, setFormData] = useState(currentLog)
  const [saveError, setSaveError] = useState('')
  const navigate = useNavigate()

  useEffect(() => {
    setFormData(currentLog)
    setSaveError('')
  }, [currentLog])

  function updateField(field, value) {
    if (hasLogToday) return
    setFormData((current) => ({ ...current, [field]: value }))
  }

  function updatePerformance(field, value) {
    if (hasLogToday) return
    setFormData((current) => ({ ...current, performance: { ...current.performance, [field]: value } }))
  }

  function toggleChecklist(key) {
    if (hasLogToday) return
    setFormData((current) => ({
      ...current,
      workoutChecklist: {
        ...current.workoutChecklist,
        [key]: !current.workoutChecklist[key],
      },
    }))
  }

  async function handleSubmit(event) {
    event.preventDefault()
    if (!formData.weight || !formData.dietFollowed) {
      setSaveError('Please complete weight and diet before saving today’s check-in.')
      return
    }

    const saved = await onSaveLog(formData)
    if (!saved) {
      setSaveError('Could not save today’s check-in. Please try again.')
      return
    }

    setSaveError('')
    navigate('/dashboard')
  }

  const completedCount = getCompletedExerciseCount(formData)

  return (
    <div className="page-stack">
      <Card className="p-5">
        <SectionHeading eyebrow="Daily log" title="Complete today’s check-in" description="One clean submission per day, synced to your account." />
        <div className="mt-4 grid gap-4">
          <InfoRow label="Date" value={TODAY_LOG_KEY} />
          <InfoRow label="Saved entries" value={String(savedCount)} />
          <FormInput label="Weight (kg)" value={formData.weight} onChange={(value) => updateField('weight', value)} placeholder="75" inputMode="decimal" disabled={hasLogToday} />
          <ChoicePillGroup label="Diet followed" value={formData.dietFollowed} onChange={(value) => updateField('dietFollowed', value)} disabled={hasLogToday} />
        </div>
      </Card>

      <Card className="p-5">
        <SectionHeading eyebrow="Workout" title="Checklist progress" description="Mark each exercise in its own row and track visible completion progress." />
        <div className="mt-4 space-y-4">
          <ProgressBar current={completedCount} total={5} />
          <WorkoutChecklistCard template={workoutPlan} checklist={formData.workoutChecklist} onToggle={toggleChecklist} disabled={hasLogToday} />
        </div>
      </Card>

      <Card className="p-5">
        <SectionHeading eyebrow="Performance" title="Log reps and cardio" description="Store enough detail for progression and coaching rules." />
        <div className="mt-4 grid gap-4 sm:grid-cols-3">
          <FormInput label="Pushups" value={formData.performance.pushups} onChange={(value) => updatePerformance('pushups', value)} placeholder="8" inputMode="numeric" disabled={hasLogToday} />
          <FormInput label="Squats" value={formData.performance.squats} onChange={(value) => updatePerformance('squats', value)} placeholder="15" inputMode="numeric" disabled={hasLogToday} />
          <FormInput label="Plank sec" value={formData.performance.plankSeconds} onChange={(value) => updatePerformance('plankSeconds', value)} placeholder="30" inputMode="numeric" disabled={hasLogToday} />
        </div>
        <div className="mt-4">
          <FormInput label="Cardio minutes" value={formData.cardioMinutes} onChange={(value) => updateField('cardioMinutes', value)} placeholder="20" inputMode="numeric" disabled={hasLogToday} />
        </div>
        {hasLogToday ? <div className="mt-4"><InlineBanner tone="success" title="Today already saved" message="Your daily check-in is locked to prevent duplicates." /></div> : null}
        {saveError ? <div className="mt-4"><InlineBanner tone="danger" title="Save issue" message={saveError} /></div> : null}
        <button type="button" onClick={handleSubmit} disabled={hasLogToday} className="primary-button mt-5 w-full disabled:cursor-not-allowed disabled:opacity-50">
          {hasLogToday ? 'Today already saved' : 'Save today’s check-in'}
        </button>
      </Card>
    </div>
  )
}

function PlanPage({ coachInsights }) {
  const rows = [
    ['Pushups', `${coachInsights.dailyWorkoutPlan.pushups.label}: ${coachInsights.dailyWorkoutPlan.pushups.prescription}`],
    ['Squats', coachInsights.dailyWorkoutPlan.squats.prescription],
    ['Plank', coachInsights.dailyWorkoutPlan.plank.prescription],
    ['Lunges', coachInsights.dailyWorkoutPlan.lunges.prescription],
    ['Cardio', coachInsights.dailyWorkoutPlan.cardio.prescription],
  ]

  return (
    <Card className="p-5">
      <SectionHeading eyebrow="Plan" title="Today’s workout prescription" description="Clean structure, clear reps, and spacing tuned for mobile use." />
      <div className="mt-4 space-y-3">
        {rows.map(([label, value]) => <InfoRow key={label} label={label} value={value} />)}
      </div>
    </Card>
  )
}

function CoachPage({ coachInsights }) {
  const tags = [
    coachInsights.lowStrength ? 'Low recent performance' : null,
    coachInsights.weightNotDropping ? 'Weight not dropping' : null,
    coachInsights.streakHigh ? 'High streak' : null,
  ].filter(Boolean)

  return (
    <div className="page-stack">
      <Card className="p-5">
        <SectionHeading eyebrow="Advice" title={coachInsights.adviceMessage} description="Rule-based coaching with simple, readable output." />
        <div className="mt-4 rounded-3xl border border-cyan-400/20 bg-cyan-400/10 p-4 text-sm whitespace-pre-line text-cyan-50">
          {coachInsights.readablePlan}
        </div>
      </Card>

      <Card className="p-5">
        <SectionHeading eyebrow="Rules" title="Triggered conditions" description="Why the coach is suggesting this plan right now." />
        <div className="mt-4 flex flex-wrap gap-2">
          {tags.length ? tags.map((tag) => <span key={tag} className="chip">{tag}</span>) : <EmptyState title="No escalations" message="No special rules were triggered from the latest data." />}
        </div>
      </Card>

      <Card className="p-5">
        <SectionHeading eyebrow="Recommendations" title="Today’s focus" description="Keep the guidance practical and easy to act on." />
        <div className="mt-4 space-y-3">
          {coachInsights.recommendations.map((item) => (
            <div key={item} className="info-row">
              <span className="status-dot" />
              <span className="text-sm text-slate-200">{item}</span>
            </div>
          ))}
        </div>
      </Card>
    </div>
  )
}

function OnboardingPage({ initialProfile, onSave }) {
  const [formData, setFormData] = useState(initialProfile)
  const [saveError, setSaveError] = useState('')
  const navigate = useNavigate()

  useEffect(() => {
    setFormData(initialProfile)
  }, [initialProfile])

  function updateField(field, value) {
    setFormData((current) => ({ ...current, [field]: value }))
  }

  async function handleSubmit(event) {
    event.preventDefault()
    if (!formData.age || !formData.height || !formData.weight) {
      setSaveError('Please fill in age, height, and weight before continuing.')
      return
    }

    const saved = await onSave(formData)
    if (!saved) {
      setSaveError('Could not save your profile. Please try again.')
      return
    }

    setSaveError('')
    navigate('/dashboard', { replace: true })
  }

  return (
    <Card className="p-5 sm:p-6">
      <SectionHeading eyebrow="Profile" title="Set up your synced profile" description="Your age, height, weight, and level are saved to Firestore and used for plan generation." />
      <form className="mt-5 space-y-4" onSubmit={handleSubmit}>
        <FormInput label="Age" value={formData.age} onChange={(value) => updateField('age', value)} placeholder="28" inputMode="numeric" />
        <FormInput label="Height (cm)" value={formData.height} onChange={(value) => updateField('height', value)} placeholder="170" inputMode="numeric" />
        <FormInput label="Weight (kg)" value={formData.weight} onChange={(value) => updateField('weight', value)} placeholder="75" inputMode="decimal" />
        <ChoicePillGroup label="Fitness level" value={formData.fitnessLevel} onChange={(value) => updateField('fitnessLevel', value)} options={['beginner', 'intermediate']} />
        {saveError ? <InlineBanner tone="danger" title="Profile issue" message={saveError} /> : null}
        <button type="submit" className="primary-button w-full">Save profile</button>
      </form>
    </Card>
  )
}

function Card({ children, className = '' }) {
  return <section className={`rounded-[28px] border border-white/10 bg-slate-950/70 shadow-[0_20px_60px_rgba(2,8,23,0.35)] backdrop-blur ${className}`}>{children}</section>
}

function SectionHeading({ eyebrow, title, description }) {
  return (
    <div>
      <p className="eyebrow">{eyebrow}</p>
      <h2 className="section-title mt-2">{title}</h2>
      <p className="section-copy mt-2">{description}</p>
    </div>
  )
}

function StatTile({ label, value, tone = 'neutral' }) {
  const toneClass = tone === 'primary' ? 'bg-cyan-400/10 border-cyan-400/20' : 'bg-white/5 border-white/10'
  return (
    <div className={`rounded-2xl border p-4 ${toneClass}`}>
      <p className="text-xs uppercase tracking-[0.18em] text-slate-400">{label}</p>
      <p className="mt-2 text-lg font-semibold capitalize text-white">{value}</p>
    </div>
  )
}

function InlineBanner({ tone, title, message }) {
  const styles = {
    info: 'border-cyan-400/20 bg-cyan-400/10 text-cyan-50',
    success: 'border-emerald-400/20 bg-emerald-400/10 text-emerald-50',
    warning: 'border-amber-400/20 bg-amber-400/10 text-amber-50',
    danger: 'border-rose-400/20 bg-rose-400/10 text-rose-50',
  }

  return (
    <div className={`rounded-2xl border px-4 py-3 ${styles[tone]}`}>
      <p className="text-sm font-semibold">{title}</p>
      <p className="mt-1 text-sm opacity-90">{message}</p>
    </div>
  )
}

function InfoRow({ label, value }) {
  return (
    <div className="info-row">
      <span className="text-sm text-slate-300">{label}</span>
      <span className="text-right text-sm font-semibold text-white">{value}</span>
    </div>
  )
}

function FormInput({ label, value, onChange, placeholder, inputMode = 'text', disabled = false }) {
  return (
    <label className="block">
      <span className="mb-2 block text-sm font-medium text-slate-200">{label}</span>
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        inputMode={inputMode}
        disabled={disabled}
        className="input-base"
      />
    </label>
  )
}

function ChoicePillGroup({ label, value, onChange, options = ['yes', 'no'], disabled = false }) {
  return (
    <div>
      <span className="mb-2 block text-sm font-medium text-slate-200">{label}</span>
      <div className="grid grid-cols-2 gap-3">
        {options.map((option) => {
          const active = value === option
          return (
            <button
              key={option}
              type="button"
              disabled={disabled}
              onClick={() => onChange(option)}
              className={`rounded-2xl border px-4 py-3 text-sm font-semibold capitalize transition ${active ? 'border-cyan-400 bg-cyan-400 text-slate-950' : 'border-white/10 bg-white/5 text-slate-200'} ${disabled ? 'opacity-60' : ''}`}
            >
              {option}
            </button>
          )
        })}
      </div>
    </div>
  )
}

function ProgressBar({ current, total }) {
  const progress = total ? Math.round((current / total) * 100) : 0
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-sm text-slate-300">
        <span>Completion progress</span>
        <span className="font-semibold text-white">{current}/{total}</span>
      </div>
      <div className="h-3 overflow-hidden rounded-full bg-white/10">
        <div className="h-full rounded-full bg-gradient-to-r from-cyan-400 to-emerald-400 transition-all duration-300" style={{ width: `${progress}%` }} />
      </div>
    </div>
  )
}

function WorkoutChecklistCard({ template, checklist, onToggle, disabled }) {
  const items = [
    { key: 'pushups', title: template.pushups.label, detail: template.pushups.prescription },
    { key: 'squats', title: 'Squats', detail: template.squats.prescription },
    { key: 'plank', title: 'Plank', detail: template.plank.prescription },
    { key: 'lunges', title: 'Lunges', detail: template.lunges.prescription },
    { key: 'cardio', title: 'Cardio', detail: template.cardio.prescription },
  ]

  return (
    <div className="space-y-3">
      {items.map((item) => (
        <label key={item.key} className="checklist-row">
          <div className="flex min-w-0 items-center gap-3">
            <input type="checkbox" checked={checklist[item.key]} disabled={disabled} onChange={() => onToggle(item.key)} className="h-5 w-5 shrink-0 accent-cyan-400" />
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-white">{item.title}</p>
              <p className="text-xs text-slate-400">{item.detail}</p>
            </div>
          </div>
          <span className={`rounded-full px-3 py-1 text-xs font-semibold ${checklist[item.key] ? 'bg-emerald-400/15 text-emerald-200' : 'bg-white/5 text-slate-300'}`}>
            {checklist[item.key] ? 'Done' : 'Pending'}
          </span>
        </label>
      ))}
    </div>
  )
}

function WeightTrendChart({ chartData }) {
  if (!chartData.length) {
    return <EmptyState title="No graph data yet" message="Save weigh-ins to render your weight trend graph." />
  }

  return (
    <div className="h-60 rounded-3xl border border-white/10 bg-slate-950/70 p-3">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={chartData}>
          <defs>
            <linearGradient id="weightFill" x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor="#22d3ee" stopOpacity={0.35} />
              <stop offset="100%" stopColor="#22d3ee" stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="rgba(148,163,184,0.12)" vertical={false} />
          <XAxis dataKey="date" tickLine={false} axisLine={false} tick={{ fill: '#94a3b8', fontSize: 11 }} />
          <YAxis hide />
          <Tooltip contentStyle={{ background: '#020617', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 18 }} labelStyle={{ color: '#cbd5e1' }} itemStyle={{ color: '#ecfeff' }} />
          <Area type="monotone" dataKey="weight" stroke="#22d3ee" strokeWidth={3} fill="url(#weightFill)" />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}

function EmptyState({ title, message }) {
  return (
    <div className="rounded-3xl border border-dashed border-white/10 bg-white/5 p-6 text-center">
      <p className="text-sm font-semibold text-white">{title}</p>
      <p className="mt-2 text-sm text-slate-400">{message}</p>
    </div>
  )
}

function BottomNav() {
  return (
    <nav className="sticky bottom-4 grid grid-cols-4 gap-2 rounded-[28px] border border-white/10 bg-slate-950/85 p-2 backdrop-blur">
      {tabs.map((tab) => (
        <NavLink
          key={tab.path}
          to={tab.path}
          className={({ isActive }) => `rounded-2xl px-2 py-3 text-center text-xs font-semibold transition ${isActive ? 'bg-cyan-400 text-slate-950' : 'text-slate-300 hover:bg-white/5'}`}
        >
          {tab.name}
        </NavLink>
      ))}
    </nav>
  )
}

export default App
