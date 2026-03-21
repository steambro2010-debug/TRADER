import { useEffect, useMemo, useState } from 'react'
import { NavLink, Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

const PROFILE_STORAGE_KEY = 'cut-tracker-profile'
const DAILY_LOGS_STORAGE_KEY = 'cut-tracker-daily-logs'
const PROGRESS_PHOTO_STORAGE_KEY = 'cut-tracker-progress-photo'
const TODAY_LOG_KEY = new Date().toISOString().slice(0, 10)
const DAY_IN_MS = 24 * 60 * 60 * 1000

const tabs = [
  {
    name: 'Dashboard',
    path: '/dashboard',
    eyebrow: 'Day 12 of 30',
    title: 'Stay sharp and consistent.',
    description: 'A quick read on your momentum, recovery, and cut adherence in one place.',
  },
  {
    name: 'Check-in',
    path: '/check-in',
    eyebrow: 'Daily ritual',
    title: 'Log the essentials once per day.',
    description: 'Track weight, workout completion, and diet adherence with a single locked daily check-in.',
  },
  {
    name: 'Plan',
    path: '/plan',
    eyebrow: 'Your structure',
    title: 'Training, meals, and habits lined up.',
    description: 'See the daily calorie target, macro split, workout focus, and small non-negotiables at a glance.',
  },
  {
    name: 'Coach',
    path: '/coach',
    eyebrow: 'Support layer',
    title: 'A calm coach view for guidance and feedback.',
    description: 'Surface encouraging notes, simple suggestions, and weekly focus points in a modern chat-style layout.',
  },
]

const statCards = [
  ['Adherence', '86%'],
  ['Avg. steps', '9.4k'],
  ['Sleep', '7h 22m'],
]

const planItems = [
  ['Calories', '2,050 kcal'],
  ['Protein', '185 g'],
  ['Lift', 'Lower body'],
  ['Cardio', '25 min incline walk'],
]

const coachMessages = [
  ['Coach', 'Your consistency is building real momentum. Keep today simple and repeatable.'],
  ['You', 'What should I prioritize if energy dips this week?'],
  ['Coach', 'Protect sleep, keep protein high, and reduce decision fatigue with a locked-in meal flow.'],
]

const defaultProfile = {
  age: '',
  height: '',
  weight: '',
  fitnessLevel: 'beginner',
}

const defaultDailyLog = {
  date: TODAY_LOG_KEY,
  weight: '',
  workoutDone: '',
  dietFollowed: '',
}

function safeReadStorage(storageKey, fallbackValue) {
  if (typeof window === 'undefined') {
    return fallbackValue
  }

  try {
    const rawValue = window.localStorage.getItem(storageKey)
    if (!rawValue) {
      return fallbackValue
    }

    const parsedValue = JSON.parse(rawValue)
    return parsedValue ?? fallbackValue
  } catch {
    return fallbackValue
  }
}

function usePersistentState(storageKey, fallbackValue) {
  const [value, setValue] = useState(() => safeReadStorage(storageKey, fallbackValue))

  useEffect(() => {
    if (typeof window === 'undefined') {
      return
    }

    try {
      window.localStorage.setItem(storageKey, JSON.stringify(value))
    } catch {
      // Swallow persistence errors so the UI remains usable.
    }
  }, [storageKey, value])

  return [value, setValue]
}

function normalizeProfile(profile) {
  return {
    age: String(profile?.age ?? '').trim(),
    height: String(profile?.height ?? '').trim(),
    weight: String(profile?.weight ?? '').trim(),
    fitnessLevel: profile?.fitnessLevel === 'intermediate' ? 'intermediate' : 'beginner',
  }
}

function normalizeBooleanChoice(value) {
  return value === 'yes' || value === 'no' ? value : ''
}

function normalizeDailyLog(log, dateKey = TODAY_LOG_KEY) {
  return {
    date: String(log?.date ?? dateKey),
    weight: String(log?.weight ?? '').trim(),
    workoutDone: normalizeBooleanChoice(log?.workoutDone),
    dietFollowed: normalizeBooleanChoice(log?.dietFollowed),
  }
}

function formatShortDate(dateKey) {
  const parsedDate = new Date(`${dateKey}T00:00:00Z`)

  if (Number.isNaN(parsedDate.getTime())) {
    return dateKey
  }

  return parsedDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric', timeZone: 'UTC' })
}

function buildWeightMetrics(dailyLogs) {
  const entries = Object.entries(dailyLogs)
    .map(([dateKey, log]) => {
      const normalizedLog = normalizeDailyLog(log, dateKey)
      const weightValue = Number.parseFloat(normalizedLog.weight)

      return {
        ...normalizedLog,
        dateKey,
        timestamp: new Date(`${dateKey}T00:00:00Z`).getTime(),
        weightValue: Number.isFinite(weightValue) ? weightValue : null,
      }
    })
    .filter((entry) => Number.isFinite(entry.timestamp))
    .sort((left, right) => left.timestamp - right.timestamp)

  const entriesWithWeight = entries.filter((entry) => entry.weightValue !== null)
  const latestEntry = entriesWithWeight.at(-1) ?? null
  const previousEntry = entriesWithWeight.at(-2) ?? null

  let streakCount = 0
  for (let index = entries.length - 1; index >= 0; index -= 1) {
    if (index === entries.length - 1) {
      streakCount = 1
      continue
    }

    const currentEntry = entries[index]
    const nextEntry = entries[index + 1]
    if (nextEntry.timestamp - currentEntry.timestamp === DAY_IN_MS) {
      streakCount += 1
    } else {
      break
    }
  }

  const weightTrendDelta = latestEntry && previousEntry ? latestEntry.weightValue - previousEntry.weightValue : null
  const trendDirection = weightTrendDelta === null ? 'flat' : weightTrendDelta > 0 ? 'up' : weightTrendDelta < 0 ? 'down' : 'flat'

  const chartData = entriesWithWeight.map((entry) => ({
    date: formatShortDate(entry.dateKey),
    weight: entry.weightValue,
  }))

  const startingEntry = entriesWithWeight[0] ?? null
  const recentSevenWeights = entriesWithWeight.slice(-7)
  const sevenDayDelta = recentSevenWeights.length >= 2
    ? recentSevenWeights.at(-1).weightValue - recentSevenWeights[0].weightValue
    : null

  const totalWeightLostValue = startingEntry && latestEntry ? startingEntry.weightValue - latestEntry.weightValue : null
  const estimatedFatLossPercentValue = startingEntry && totalWeightLostValue !== null && startingEntry.weightValue > 0
    ? (totalWeightLostValue / startingEntry.weightValue) * 100
    : null
  const progressPercent = estimatedFatLossPercentValue === null ? 0 : Math.max(0, Math.min((estimatedFatLossPercentValue / 5) * 100, 100))

  let sevenDayStatus = 'Need more data'
  if (sevenDayDelta !== null) {
    if (sevenDayDelta < -0.2) {
      sevenDayStatus = 'On track'
    } else if (sevenDayDelta > 0.2) {
      sevenDayStatus = "You're overeating"
    } else {
      sevenDayStatus = 'Adjust diet'
    }
  }

  return {
    latestWeight: latestEntry ? `${latestEntry.weight} lb` : '--',
    streakCount: entries.length ? streakCount : 0,
    trendDirection,
    trendLabel:
      weightTrendDelta === null
        ? 'Need 2 weigh-ins'
        : `${weightTrendDelta > 0 ? '+' : ''}${weightTrendDelta.toFixed(1)} lb`,
    totalWeightLost: totalWeightLostValue === null ? '--' : `${totalWeightLostValue.toFixed(1)} lb`,
    estimatedFatLossPercent: estimatedFatLossPercentValue === null ? '--' : `${estimatedFatLossPercentValue.toFixed(1)}%`,
    progressPercent,
    sevenDayDelta,
    sevenDayStatus,
    chartData,
  }
}

function buildAlerts(dailyLogs, weightMetrics) {
  const sortedDates = Object.keys(dailyLogs).sort()
  const latestDate = sortedDates.at(-1) ?? null
  const alerts = []

  if (latestDate) {
    const latestTimestamp = new Date(`${latestDate}T00:00:00Z`).getTime()
    const todayTimestamp = new Date(`${TODAY_LOG_KEY}T00:00:00Z`).getTime()
    const daysSinceLastEntry = Math.floor((todayTimestamp - latestTimestamp) / DAY_IN_MS)

    if (daysSinceLastEntry >= 2) {
      alerts.push({ type: 'warning', title: 'No entry for 2 days', message: 'Log today to get your trend and coaching back on track.' })
    }

    if (weightMetrics.streakCount <= 1 && sortedDates.length > 1 && daysSinceLastEntry >= 1) {
      alerts.push({ type: 'alert', title: 'Streak broken', message: "Your logging streak has broken. Restart with today's check-in." })
    }
  }

  return alerts
}

function buildWeeklySummary(dailyLogs) {
  const recentEntries = Object.entries(dailyLogs)
    .map(([dateKey, log]) => normalizeDailyLog(log, dateKey))
    .sort((left, right) => left.date.localeCompare(right.date))
    .slice(-7)

  return {
    checkIns: recentEntries.length,
    workouts: recentEntries.filter((entry) => entry.workoutDone === 'yes').length,
    dietHits: recentEntries.filter((entry) => entry.dietFollowed === 'yes').length,
  }
}

function buildCoachInsights(profile, dailyLogs, weightMetrics) {
  const recentEntries = Object.entries(dailyLogs)
    .map(([dateKey, log]) => ({ ...normalizeDailyLog(log, dateKey), dateKey }))
    .sort((left, right) => left.dateKey.localeCompare(right.dateKey))
    .slice(-7)

  const workoutsDoneCount = recentEntries.filter((entry) => entry.workoutDone === 'yes').length
  const lowStrength = profile.fitnessLevel === 'beginner' && workoutsDoneCount <= 2
  const weightNotDropping = weightMetrics.sevenDayStatus === 'Adjust diet' || weightMetrics.sevenDayStatus === "You're overeating"
  const streakHigh = weightMetrics.streakCount >= 5

  let dailyWorkoutPlan = {
    focus: 'Full-body lift',
    intensity: 'Moderate',
    cardio: '15 mins incline walk',
  }
  let adviceMessage = weightMetrics.sevenDayStatus === 'Need more data' ? "You're on track" : weightMetrics.sevenDayStatus
  const recommendations = ["Keep protein high and stay consistent today."]

  if (lowStrength) {
    dailyWorkoutPlan = {
      focus: 'Technique-based full body session',
      intensity: 'Easy',
      cardio: '10 mins incline walk',
    }
    adviceMessage = 'Start with an easier plan to build consistency.'
    recommendations[0] = 'Keep weights light, focus on form, and leave 2-3 reps in reserve.'
  }

  if (weightNotDropping) {
    adviceMessage = 'Reduce carbs slightly.'
    recommendations.push('Reduce carbs slightly and tighten portions at your next two meals.')
    dailyWorkoutPlan.cardio = 'Increase cardio to 20 mins'
  }

  if (streakHigh) {
    adviceMessage = 'Increase intensity today.'
    recommendations.push('Your streak is high, so add one extra set or push pace on your finisher.')
    dailyWorkoutPlan.intensity = lowStrength ? 'Moderate' : 'Hard'
    if (!weightNotDropping) {
      dailyWorkoutPlan.cardio = 'Increase cardio to 20 mins'
    }
  }

  return {
    lowStrength,
    weightNotDropping,
    streakHigh,
    adviceMessage,
    dailyWorkoutPlan,
    recommendations,
    sevenDayStatus: weightMetrics.sevenDayStatus,
  }
}

function PhoneShell({ children, className = '' }) {
  return (
    <div className={`mx-auto flex min-h-screen w-full max-w-sm flex-col bg-slate-950 text-slate-50 shadow-2xl shadow-cyan-950/30 ${className}`}>
      {children}
    </div>
  )
}

function AppHeader({ profile }) {
  const location = useLocation()
  const activeTab = tabs.find((tab) => location.pathname.startsWith(tab.path)) ?? tabs[0]

  return (
    <header className="relative overflow-hidden border-b border-white/10 px-5 pb-6 pt-8">
      <div className="absolute inset-x-0 top-0 h-40 bg-gradient-to-b from-cyan-500/20 via-teal-400/10 to-transparent" />
      <div className="relative">
        <div className="flex items-center justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-[0.28em] text-cyan-300">30 Day Cut Tracker</p>
            <h1 className="mt-3 text-3xl font-semibold tracking-tight text-white">{activeTab.name}</h1>
          </div>
          <div className="rounded-2xl border border-cyan-400/30 bg-cyan-400/10 px-3 py-2 text-right">
            <p className="text-[10px] uppercase tracking-[0.22em] text-cyan-200/80">Profile</p>
            <p className="mt-1 text-sm font-semibold text-cyan-50">{profile.weight || '--'} lb</p>
            <p className="text-xs text-cyan-100/70 capitalize">{profile.fitnessLevel}</p>
          </div>
        </div>
        <p className="mt-4 max-w-xs text-sm leading-6 text-slate-300">{activeTab.description}</p>
      </div>
    </header>
  )
}

function SectionCard({ eyebrow, title, description, children }) {
  return (
    <section className="rounded-3xl border border-white/10 bg-white/5 p-5 backdrop-blur-sm">
      <p className="text-xs font-semibold uppercase tracking-[0.24em] text-cyan-300">{eyebrow}</p>
      <h2 className="mt-3 text-xl font-semibold text-white">{title}</h2>
      <p className="mt-2 text-sm leading-6 text-slate-300">{description}</p>
      <div className="mt-5">{children}</div>
    </section>
  )
}

function ProfileSnapshot({ profile }) {
  const items = [
    ['Age', profile.age],
    ['Height', profile.height],
    ['Weight', profile.weight],
    ['Level', profile.fitnessLevel],
  ]

  return (
    <div className="grid grid-cols-2 gap-3">
      {items.map(([label, value]) => (
        <div key={label} className="rounded-2xl border border-white/10 bg-slate-900/80 p-4">
          <p className="text-xs text-slate-400">{label}</p>
          <p className="mt-2 text-lg font-semibold capitalize text-white">{value || '--'}</p>
        </div>
      ))}
    </div>
  )
}

function WeightTrendChart({ chartData }) {
  if (!chartData.length) {
    return (
      <div className="flex h-48 items-center justify-center rounded-2xl border border-dashed border-white/10 bg-slate-900/70 text-sm text-slate-400">
        Save weigh-ins to see your weight trend graph.
      </div>
    )
  }

  return (
    <div className="h-48 rounded-2xl border border-white/10 bg-slate-900/70 p-3">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={chartData}>
          <defs>
            <linearGradient id="weightFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#22d3ee" stopOpacity={0.4} />
              <stop offset="95%" stopColor="#22d3ee" stopOpacity={0.04} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="rgba(148, 163, 184, 0.12)" vertical={false} />
          <XAxis dataKey="date" tickLine={false} axisLine={false} tick={{ fill: '#94a3b8', fontSize: 11 }} />
          <YAxis hide domain={['dataMin - 1', 'dataMax + 1']} />
          <Tooltip
            contentStyle={{ background: '#0f172a', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 16 }}
            labelStyle={{ color: '#cbd5e1' }}
            itemStyle={{ color: '#ecfeff' }}
          />
          <Area type="monotone" dataKey="weight" stroke="#22d3ee" strokeWidth={3} fill="url(#weightFill)" />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}

function DashboardPage({ profile, metrics, alerts, weeklySummary, progressPhoto, onPhotoUpload }) {
  const page = tabs[0]
  const metricCards = [
    ['Latest weight', metrics.latestWeight],
    ['Total lost', metrics.totalWeightLost],
    ['Fat loss %', metrics.estimatedFatLossPercent],
    ['7-day status', metrics.sevenDayStatus],
  ]

  return (
    <div className="space-y-4">
      <SectionCard eyebrow="Your setup" title="Profile locked in." description="Your baseline stats are saved locally so the tracker can personalize future coaching and planning flows.">
        <ProfileSnapshot profile={profile} />
      </SectionCard>
      {alerts.length ? (
        <div className="space-y-3">
          {alerts.map((alert) => (
            <div key={alert.title} className={`alert-pulse rounded-2xl border px-4 py-4 text-sm ${alert.type === 'warning' ? 'border-amber-400/30 bg-amber-400/10 text-amber-50' : 'border-rose-400/30 bg-rose-400/10 text-rose-100'}`}>
              <p className="font-semibold">{alert.title}</p>
              <p className="mt-1">{alert.message}</p>
            </div>
          ))}
        </div>
      ) : null}
      <SectionCard eyebrow="Real data" title="Dashboard synced to stored check-ins." description="These cards and the graph below are computed from your saved local check-in history.">
        <div className="grid grid-cols-2 gap-3">
          {metricCards.map(([label, value]) => (
            <div key={label} className="rounded-2xl border border-white/10 bg-slate-900/80 p-4">
              <p className="text-xs text-slate-400">{label}</p>
              <p className="mt-2 text-lg font-semibold capitalize text-white">{value}</p>
            </div>
          ))}
        </div>
      </SectionCard>
      <SectionCard eyebrow="Progress" title="Visual progress feedback." description="Simple progress uses estimated fat loss percentage toward a 5% milestone.">
        <div className="rounded-2xl border border-white/10 bg-slate-900/80 p-4">
          <div className="flex items-center justify-between text-sm text-slate-300">
            <span>Estimated fat loss</span>
            <span className="font-semibold text-white">{metrics.estimatedFatLossPercent}</span>
          </div>
          <div className="mt-3 h-3 overflow-hidden rounded-full bg-white/10">
            <div className="h-full rounded-full bg-gradient-to-r from-cyan-400 to-emerald-400 transition-all duration-500" style={{ width: `${metrics.progressPercent}%` }} />
          </div>
          <p className="mt-3 text-sm text-slate-300">
            {metrics.progressPercent >= 100 ? 'Strong progress—goal range reached.' : 'Keep stacking daily check-ins to move the bar.'}
          </p>
        </div>
      </SectionCard>
      <SectionCard eyebrow="Weekly summary" title="Last 7 days at a glance." description="A simple roll-up of your recent consistency.">
        <div className="grid grid-cols-3 gap-3">
          {[['Check-ins', String(weeklySummary.checkIns)], ['Workouts', String(weeklySummary.workouts)], ['Diet hits', String(weeklySummary.dietHits)]].map(([label, value]) => (
            <div key={label} className="glow-card rounded-2xl border border-white/10 bg-slate-900/80 p-4">
              <p className="text-xs text-slate-400">{label}</p>
              <p className="mt-2 text-lg font-semibold text-white">{value}</p>
            </div>
          ))}
        </div>
      </SectionCard>
      <SectionCard eyebrow="Progress photo" title="Upload a visual check-in." description="Store a simple comparison photo locally on this device.">
        <div className="space-y-4">
          <label className="block rounded-2xl border border-dashed border-white/10 bg-slate-900/70 p-4 text-sm text-slate-300">
            <span className="mb-3 block font-medium text-white">Choose a photo</span>
            <input type="file" accept="image/*" onChange={onPhotoUpload} className="block w-full text-xs text-slate-400" />
          </label>
          {progressPhoto ? <img src={progressPhoto} alt="Progress upload" className="glow-card h-48 w-full rounded-2xl object-cover" /> : <div className="rounded-2xl border border-dashed border-white/10 bg-slate-900/70 p-6 text-center text-sm text-slate-400">Upload a photo to keep a local visual reference.</div>}
        </div>
      </SectionCard>
      <SectionCard eyebrow="Weight graph" title="Trend line from real entries." description="Each plotted point comes from a stored daily log with a saved weight value.">
        <WeightTrendChart chartData={metrics.chartData} />
      </SectionCard>
      <SectionCard eyebrow={page.eyebrow} title={page.title} description={page.description}>
        <div className="grid grid-cols-3 gap-3">
          {statCards.map(([label, value]) => (
            <div key={label} className="rounded-2xl border border-white/10 bg-slate-900/80 p-4">
              <p className="text-xs text-slate-400">{label}</p>
              <p className="mt-2 text-lg font-semibold text-white">{value}</p>
            </div>
          ))}
        </div>
      </SectionCard>
    </div>
  )
}

function ChoicePillGroup({ label, value, onChange, disabled = false }) {
  return (
    <div>
      <label className="mb-2 block text-sm font-medium text-slate-200">{label}</label>
      <div className="grid grid-cols-2 gap-3">
        {['yes', 'no'].map((choice) => {
          const active = value === choice

          return (
            <button
              key={choice}
              type="button"
              disabled={disabled}
              onClick={() => onChange(choice)}
              className={`rounded-2xl border px-4 py-4 text-sm font-semibold capitalize transition-all duration-300 ${
                active
                  ? 'border-cyan-400 bg-cyan-400 text-slate-950 shadow-lg shadow-cyan-500/20'
                  : 'border-white/10 bg-slate-900/80 text-slate-300'
              } ${disabled ? 'cursor-not-allowed opacity-60' : ''}`}
            >
              {choice}
            </button>
          )
        })}
      </div>
    </div>
  )
}

function CheckInPage({ currentLog, hasLogToday, onSaveLog, savedCount }) {
  const page = tabs[1]
  const [formData, setFormData] = useState(currentLog)
  const [saveError, setSaveError] = useState('')

  useEffect(() => {
    setFormData(currentLog)
    setSaveError('')
  }, [currentLog])

  function updateField(field, value) {
    if (hasLogToday) {
      return
    }

    setFormData((current) => ({ ...current, [field]: value }))
  }

  function handleSubmit(event) {
    event.preventDefault()

    if (hasLogToday) {
      setSaveError('A check-in for today already exists. Duplicate entries are disabled.')
      return
    }

    if (!formData.weight || !formData.workoutDone || !formData.dietFollowed) {
      setSaveError('Please complete weight, workout, and diet before saving today\'s check-in.')
      return
    }

    const saved = onSaveLog(formData)

    if (!saved) {
      setSaveError('A check-in for today already exists. Duplicate entries are disabled.')
      return
    }

    setSaveError('')
  }

  return (
    <SectionCard eyebrow={page.eyebrow} title={page.title} description={page.description}>
      <form className="grid gap-4" onSubmit={handleSubmit}>
        <div className="rounded-2xl border border-white/10 bg-slate-900/70 p-4 text-sm text-slate-300">
          <p className="font-semibold text-white">Date</p>
          <p className="mt-1">{TODAY_LOG_KEY}</p>
          <p className="mt-3 text-xs text-slate-400">Only one check-in can be saved for each date.</p>
        </div>

        <FormInput
          label="Weight"
          value={formData.weight}
          onChange={(value) => updateField('weight', value)}
          placeholder="184.6"
          inputMode="decimal"
          disabled={hasLogToday}
        />

        <ChoicePillGroup
          label="Workout done"
          value={formData.workoutDone}
          onChange={(value) => updateField('workoutDone', value)}
          disabled={hasLogToday}
        />

        <ChoicePillGroup
          label="Diet followed"
          value={formData.dietFollowed}
          onChange={(value) => updateField('dietFollowed', value)}
          disabled={hasLogToday}
        />

        <div className={`rounded-2xl border p-4 text-sm ${hasLogToday ? 'border-emerald-400/20 bg-emerald-400/10 text-emerald-50' : 'border-white/10 bg-slate-900/70 text-slate-300'}`}>
          <p className="font-semibold text-white">Saved daily logs: {savedCount}</p>
          <p className="mt-1">
            {hasLogToday
              ? 'Today\'s check-in is already saved and locked to prevent duplicates.'
              : 'Today\'s entry will be stored in localStorage and restored after refresh.'}
          </p>
        </div>

        {saveError ? (
          <div className="rounded-2xl border border-rose-400/20 bg-rose-400/10 p-4 text-sm text-rose-100">{saveError}</div>
        ) : null}

        <button
          disabled={hasLogToday}
          className={`rounded-2xl px-4 py-4 text-center text-sm font-semibold transition-transform duration-300 ${
            hasLogToday
              ? 'cursor-not-allowed bg-slate-700 text-slate-400'
              : 'bg-cyan-400 text-slate-950 hover:-translate-y-0.5'
          }`}
        >
          {hasLogToday ? 'Today already saved' : 'Save today\'s check-in'}
        </button>
      </form>
    </SectionCard>
  )
}

function PlanPage({ coachInsights }) {
  const page = tabs[2]
  const planRows = [
    ['Workout focus', coachInsights.dailyWorkoutPlan.focus],
    ['Intensity', coachInsights.dailyWorkoutPlan.intensity],
    ['Cardio', coachInsights.dailyWorkoutPlan.cardio],
    ['Nutrition note', coachInsights.weightNotDropping ? 'Reduce carbs slightly' : 'Keep meals steady'],
  ]

  return (
    <SectionCard eyebrow={page.eyebrow} title={page.title} description={page.description}>
      <div className="space-y-3">
        {planRows.map(([label, value]) => (
          <div key={label} className="flex items-center justify-between rounded-2xl border border-white/10 bg-slate-900/80 px-4 py-3">
            <span className="text-sm text-slate-300">{label}</span>
            <span className="text-right text-sm font-semibold text-white">{value}</span>
          </div>
        ))}
      </div>
    </SectionCard>
  )
}

function CoachPage({ coachInsights }) {
  const page = tabs[3]
  const ruleTags = [
    coachInsights.lowStrength ? 'Beginner + low strength' : null,
    coachInsights.weightNotDropping ? 'Weight not dropping' : null,
    coachInsights.streakHigh ? 'High streak' : null,
  ].filter(Boolean)

  return (
    <div className="space-y-4">
      <SectionCard eyebrow={page.eyebrow} title={page.title} description={page.description}>
        <div className="rounded-2xl border border-cyan-400/20 bg-cyan-400/10 p-4">
          <p className="text-xs uppercase tracking-[0.24em] text-cyan-200">Advice message</p>
          <p className="mt-2 text-lg font-semibold text-white">{coachInsights.adviceMessage}</p>
          <p className="mt-2 text-sm text-cyan-100/80">Last 7 days: {coachInsights.sevenDayStatus}</p>
        </div>
        <div className="mt-4 grid gap-3">
          <div className="rounded-2xl border border-white/10 bg-slate-900/80 p-4">
            <p className="text-xs uppercase tracking-[0.24em] text-slate-400">Daily workout plan</p>
            <p className="mt-2 text-sm text-white">{coachInsights.dailyWorkoutPlan.focus}</p>
            <p className="mt-1 text-sm text-slate-300">Intensity: {coachInsights.dailyWorkoutPlan.intensity}</p>
            <p className="mt-1 text-sm text-slate-300">{coachInsights.dailyWorkoutPlan.cardio}</p>
          </div>
          <div className="rounded-2xl border border-white/10 bg-slate-900/80 p-4">
            <p className="text-xs uppercase tracking-[0.24em] text-slate-400">Rules triggered</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {ruleTags.length ? ruleTags.map((tag) => (
                <span key={tag} className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-slate-200">{tag}</span>
              )) : <span className="text-sm text-slate-300">No escalation rules triggered.</span>}
            </div>
          </div>
          <div className="rounded-2xl border border-white/10 bg-slate-900/80 p-4">
            <p className="text-xs uppercase tracking-[0.24em] text-slate-400">Recommendations</p>
            <ul className="mt-3 space-y-2 text-sm text-slate-200">
              {coachInsights.recommendations.map((item) => (
                <li key={item} className="rounded-xl bg-white/5 px-3 py-2">{item}</li>
              ))}
            </ul>
          </div>
        </div>
      </SectionCard>

      <SectionCard eyebrow="Examples" title="Rule-based examples in action." description="Sample outputs the coach can produce from your saved profile and recent logs.">
        <div className="space-y-3">
          {['Increase cardio to 20 mins', 'Reduce carbs slightly', "You're on track"].map((message) => (
            <div key={message} className="rounded-2xl border border-white/10 bg-slate-900/80 px-4 py-3 text-sm text-slate-200">
              {message}
            </div>
          ))}
        </div>
      </SectionCard>
    </div>
  )
}

function OnboardingPage({ initialProfile, onSave }) {
  const navigate = useNavigate()
  const [formData, setFormData] = useState(initialProfile)

  useEffect(() => {
    setFormData(initialProfile)
  }, [initialProfile])

  function updateField(field, value) {
    setFormData((current) => ({ ...current, [field]: value }))
  }

  function handleSubmit(event) {
    event.preventDefault()
    onSave(formData)
    navigate('/dashboard', { replace: true })
  }

  return (
    <section className="w-full rounded-[2rem] border border-white/10 bg-white/6 p-5 backdrop-blur-xl">
      <p className="text-xs font-semibold uppercase tracking-[0.28em] text-cyan-300">Welcome</p>
      <h1 className="mt-3 text-3xl font-semibold tracking-tight text-white">Set up your cut profile.</h1>
      <p className="mt-3 text-sm leading-6 text-slate-300">
        Add a few baseline stats so the tracker can tailor future dashboards, plan suggestions, and coaching.
      </p>

      <form className="mt-6 space-y-4" onSubmit={handleSubmit}>
        <FormInput
          label="Age"
          value={formData.age}
          onChange={(value) => updateField('age', value)}
          placeholder="28"
          inputMode="numeric"
        />
        <FormInput
          label="Height"
          value={formData.height}
          onChange={(value) => updateField('height', value)}
          placeholder="5'11\""
        />
        <FormInput
          label="Weight"
          value={formData.weight}
          onChange={(value) => updateField('weight', value)}
          placeholder="185"
          inputMode="decimal"
        />

        <div>
          <label className="mb-2 block text-sm font-medium text-slate-200">Fitness level</label>
          <div className="grid grid-cols-2 gap-3">
            {['beginner', 'intermediate'].map((level) => {
              const active = formData.fitnessLevel === level

              return (
                <button
                  key={level}
                  type="button"
                  onClick={() => updateField('fitnessLevel', level)}
                  className={`rounded-2xl border px-4 py-4 text-sm font-semibold capitalize transition-all duration-300 ${
                    active
                      ? 'border-cyan-400 bg-cyan-400 text-slate-950 shadow-lg shadow-cyan-500/20'
                      : 'border-white/10 bg-slate-900/80 text-slate-300'
                  }`}
                >
                  {level}
                </button>
              )
            })}
          </div>
        </div>

        <div className="rounded-2xl border border-white/10 bg-slate-900/70 p-4 text-sm text-slate-300">
          Profile data is stored locally on this device using <span className="font-semibold text-white">localStorage</span>.
        </div>

        <button
          type="submit"
          className="w-full rounded-2xl bg-cyan-400 px-4 py-4 text-sm font-semibold text-slate-950 transition-transform duration-300 hover:-translate-y-0.5"
        >
          Save profile
        </button>
      </form>
    </section>
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
        className={`w-full rounded-2xl border px-4 py-4 text-base outline-none transition-all duration-300 placeholder:text-slate-500 ${
          disabled
            ? 'cursor-not-allowed border-white/10 bg-slate-800 text-slate-500'
            : 'border-white/10 bg-slate-900/80 text-white focus:border-cyan-400 focus:ring-2 focus:ring-cyan-400/20'
        }`}
      />
    </label>
  )
}

function AnimatedRoutes({ profile, hasProfile, dailyLogs, progressPhoto, onPhotoUpload, onSaveProfile, onSaveDailyLog }) {
  const location = useLocation()
  const dashboardMetrics = useMemo(() => buildWeightMetrics(dailyLogs), [dailyLogs])
  const coachInsights = useMemo(() => buildCoachInsights(profile, dailyLogs, dashboardMetrics), [profile, dailyLogs, dashboardMetrics])
  const alerts = useMemo(() => buildAlerts(dailyLogs, dashboardMetrics), [dailyLogs, dashboardMetrics])
  const weeklySummary = useMemo(() => buildWeeklySummary(dailyLogs), [dailyLogs])
  const hasLogToday = Boolean(dailyLogs[TODAY_LOG_KEY])
  const todayLog = normalizeDailyLog(dailyLogs[TODAY_LOG_KEY], TODAY_LOG_KEY)
  const totalLogs = Object.keys(dailyLogs).length

  return (
    <main className={`flex-1 overflow-hidden ${location.pathname === '/onboarding' ? 'px-4 py-6 flex items-center' : 'px-4 py-4'}`}>
      <div key={location.pathname} className="page-transition space-y-4">
        <Routes location={location}>
          <Route path="/" element={<Navigate to={hasProfile ? '/dashboard' : '/onboarding'} replace />} />
          <Route path="/onboarding" element={<OnboardingPage initialProfile={profile} onSave={onSaveProfile} />} />
          <Route
            path="/dashboard"
            element={hasProfile ? <DashboardPage profile={profile} metrics={dashboardMetrics} alerts={alerts} weeklySummary={weeklySummary} progressPhoto={progressPhoto} onPhotoUpload={onPhotoUpload} /> : <Navigate to="/onboarding" replace />}
          />
          <Route
            path="/check-in"
            element={
              hasProfile ? (
                <CheckInPage
                  currentLog={todayLog}
                  hasLogToday={hasLogToday}
                  onSaveLog={onSaveDailyLog}
                  savedCount={totalLogs}
                />
              ) : (
                <Navigate to="/onboarding" replace />
              )
            }
          />
          <Route path="/plan" element={hasProfile ? <PlanPage coachInsights={coachInsights} /> : <Navigate to="/onboarding" replace />} />
          <Route path="/coach" element={hasProfile ? <CoachPage coachInsights={coachInsights} /> : <Navigate to="/onboarding" replace />} />
        </Routes>
      </div>
    </main>
  )
}

function BottomNav() {
  return (
    <nav className="sticky bottom-0 grid grid-cols-4 gap-2 border-t border-white/10 bg-slate-950/90 px-3 py-3 backdrop-blur">
      {tabs.map((tab) => (
        <NavLink
          key={tab.path}
          to={tab.path}
          className={({ isActive }) =>
            `rounded-2xl px-2 py-3 text-center text-xs font-medium transition-all duration-300 ${
              isActive
                ? 'bg-cyan-400 text-slate-950 shadow-lg shadow-cyan-500/20'
                : 'bg-white/5 text-slate-300 hover:bg-white/10'
            }`
          }
        >
          {tab.name}
        </NavLink>
      ))}
    </nav>
  )
}

function AppShell({ profile, hasProfile, dailyLogs, progressPhoto, onPhotoUpload, onSaveProfile, onSaveDailyLog }) {
  const location = useLocation()
  const isOnboarding = location.pathname === '/onboarding'

  return (
    <div className="min-h-screen bg-slate-900">
      <PhoneShell className={isOnboarding ? 'justify-center' : ''}>
        {!isOnboarding && hasProfile ? <AppHeader profile={profile} /> : null}
        <AnimatedRoutes
          profile={profile}
          hasProfile={hasProfile}
          dailyLogs={dailyLogs}
          progressPhoto={progressPhoto}
          onPhotoUpload={onPhotoUpload}
          onSaveProfile={onSaveProfile}
          onSaveDailyLog={onSaveDailyLog}
        />
        {!isOnboarding && hasProfile ? <BottomNav /> : null}
      </PhoneShell>
    </div>
  )
}

function App() {
  const [profile, setProfile] = usePersistentState(PROFILE_STORAGE_KEY, defaultProfile)
  const [dailyLogs, setDailyLogs] = usePersistentState(DAILY_LOGS_STORAGE_KEY, {})
  const [progressPhoto, setProgressPhoto] = usePersistentState(PROGRESS_PHOTO_STORAGE_KEY, '')

  const normalizedProfile = useMemo(() => normalizeProfile(profile), [profile])
  const normalizedDailyLogs = useMemo(() => {
    if (!dailyLogs || typeof dailyLogs !== 'object' || Array.isArray(dailyLogs)) {
      return {}
    }

    return Object.fromEntries(
      Object.entries(dailyLogs).map(([dateKey, log]) => [dateKey, normalizeDailyLog(log, dateKey)]),
    )
  }, [dailyLogs])

  const hasProfile = Boolean(
    normalizedProfile.age && normalizedProfile.height && normalizedProfile.weight && normalizedProfile.fitnessLevel,
  )

  function handleSaveProfile(nextProfile) {
    setProfile(normalizeProfile(nextProfile))
  }

  function handleSaveDailyLog(nextLog) {
    const normalizedLog = normalizeDailyLog(nextLog, TODAY_LOG_KEY)
    let didSave = false

    setDailyLogs((currentLogs) => {
      const safeLogs = currentLogs && typeof currentLogs === 'object' && !Array.isArray(currentLogs) ? currentLogs : {}

      if (safeLogs[TODAY_LOG_KEY]) {
        return safeLogs
      }

      didSave = true
      return {
        ...safeLogs,
        [TODAY_LOG_KEY]: normalizedLog,
      }
    })

    return didSave
  }

  function handlePhotoUpload(event) {
    const file = event.target.files?.[0]
    if (!file) {
      return
    }

    const reader = new FileReader()
    reader.onload = () => {
      if (typeof reader.result === 'string') {
        setProgressPhoto(reader.result)
      }
    }
    reader.readAsDataURL(file)
  }

  return (
    <AppShell
      profile={normalizedProfile}
      hasProfile={hasProfile}
      dailyLogs={normalizedDailyLogs}
      progressPhoto={progressPhoto}
      onPhotoUpload={handlePhotoUpload}
      onSaveProfile={handleSaveProfile}
      onSaveDailyLog={handleSaveDailyLog}
    />
  )
}

export default App
