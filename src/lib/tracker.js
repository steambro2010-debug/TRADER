export const TODAY_LOG_KEY = new Date().toISOString().slice(0, 10)
const DAY_IN_MS = 24 * 60 * 60 * 1000

export const defaultProfile = {
  age: '',
  height: '',
  weight: '',
  fitnessLevel: 'beginner',
}

export const defaultDailyLog = {
  date: TODAY_LOG_KEY,
  weight: '',
  dietFollowed: '',
  cardioMinutes: '',
  workoutChecklist: {
    pushups: false,
    squats: false,
    plank: false,
    lunges: false,
    cardio: false,
  },
  performance: {
    pushups: '',
    squats: '',
    plankSeconds: '',
  },
}

export function normalizeProfile(profile) {
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

function normalizeWorkoutChecklist(checklist) {
  return {
    pushups: Boolean(checklist?.pushups),
    squats: Boolean(checklist?.squats),
    plank: Boolean(checklist?.plank),
    lunges: Boolean(checklist?.lunges),
    cardio: Boolean(checklist?.cardio),
  }
}

function normalizePerformance(performance) {
  return {
    pushups: String(performance?.pushups ?? '').trim(),
    squats: String(performance?.squats ?? '').trim(),
    plankSeconds: String(performance?.plankSeconds ?? '').trim(),
  }
}

export function normalizeDailyLog(log, dateKey = TODAY_LOG_KEY) {
  return {
    date: String(log?.date ?? dateKey),
    weight: String(log?.weight ?? '').trim(),
    dietFollowed: normalizeBooleanChoice(log?.dietFollowed),
    cardioMinutes: String(log?.cardioMinutes ?? '').trim(),
    workoutChecklist: normalizeWorkoutChecklist(log?.workoutChecklist),
    performance: normalizePerformance(log?.performance),
  }
}

export function getCompletedExerciseCount(log) {
  return Object.values(normalizeDailyLog(log).workoutChecklist).filter(Boolean).length
}

function formatShortDate(dateKey) {
  const parsedDate = new Date(`${dateKey}T00:00:00Z`)
  if (Number.isNaN(parsedDate.getTime())) return dateKey
  return parsedDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric', timeZone: 'UTC' })
}

export function buildWeightMetrics(dailyLogs) {
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
  const startingEntry = entriesWithWeight[0] ?? null
  const chartData = entriesWithWeight.map((entry) => ({ date: formatShortDate(entry.dateKey), weight: entry.weightValue }))

  let streakCount = 0
  for (let index = entries.length - 1; index >= 0; index -= 1) {
    if (index === entries.length - 1) {
      streakCount = 1
      continue
    }

    if (entries[index + 1].timestamp - entries[index].timestamp === DAY_IN_MS) streakCount += 1
    else break
  }

  const recentSevenWeights = entriesWithWeight.slice(-7)
  const sevenDayDelta = recentSevenWeights.length >= 2 ? recentSevenWeights.at(-1).weightValue - recentSevenWeights[0].weightValue : null

  let sevenDayStatus = 'Need more data'
  if (sevenDayDelta !== null) {
    if (sevenDayDelta < -0.2) sevenDayStatus = 'On track'
    else if (sevenDayDelta > 0.2) sevenDayStatus = "You're overeating"
    else sevenDayStatus = 'Adjust diet'
  }

  const totalWeightLostValue = startingEntry && latestEntry ? startingEntry.weightValue - latestEntry.weightValue : null
  const estimatedFatLossPercentValue = startingEntry && totalWeightLostValue !== null && startingEntry.weightValue > 0
    ? (totalWeightLostValue / startingEntry.weightValue) * 100
    : null
  const progressPercent = estimatedFatLossPercentValue === null ? 0 : Math.max(0, Math.min((estimatedFatLossPercentValue / 5) * 100, 100))
  const weightTrendDelta = latestEntry && previousEntry ? latestEntry.weightValue - previousEntry.weightValue : null

  return {
    latestWeight: latestEntry ? `${latestEntry.weight} kg` : '--',
    latestWeightValue: latestEntry?.weightValue ?? null,
    streakCount: entries.length ? streakCount : 0,
    trendLabel: weightTrendDelta === null ? 'Need 2 weigh-ins' : `${weightTrendDelta > 0 ? '+' : ''}${weightTrendDelta.toFixed(1)} kg`,
    totalWeightLost: totalWeightLostValue === null ? '--' : `${totalWeightLostValue.toFixed(1)} kg`,
    estimatedFatLossPercent: estimatedFatLossPercentValue === null ? '--' : `${estimatedFatLossPercentValue.toFixed(1)}%`,
    progressPercent,
    sevenDayStatus,
    chartData,
  }
}

export function buildWorkoutTemplate(profile, recentLogs, weightMetrics) {
  const latestPerformance = recentLogs.at(-1)?.performance ?? defaultDailyLog.performance
  const pushupCount = Number.parseInt(latestPerformance.pushups, 10)
  const plankSeconds = Number.parseInt(latestPerformance.plankSeconds, 10)
  const squatCount = Number.parseInt(latestPerformance.squats, 10)

  let pushupsLabel = 'Incline pushups'
  let pushupsPrescription = '4 × 8'

  if (Number.isFinite(pushupCount) && pushupCount >= 5 && pushupCount <= 15) {
    pushupsLabel = 'Normal pushups'
    pushupsPrescription = '4 × max'
  } else if (Number.isFinite(pushupCount) && pushupCount > 15) {
    pushupsLabel = 'Normal pushups'
    pushupsPrescription = `4 × ${pushupCount + 2}`
  } else if (profile.fitnessLevel === 'intermediate') {
    pushupsLabel = 'Normal pushups'
    pushupsPrescription = '4 × 10'
  }

  const nextPlankSeconds = Number.isFinite(plankSeconds)
    ? plankSeconds + (plankSeconds < 45 ? 5 : 10)
    : profile.fitnessLevel === 'intermediate' ? 35 : 25

  const squatTarget = Number.isFinite(squatCount)
    ? Math.max(15, Math.min(squatCount + 2, 30))
    : 15

  const cardioTarget = weightMetrics.sevenDayStatus === 'Adjust diet' || weightMetrics.sevenDayStatus === "You're overeating"
    ? 20
    : 15

  return {
    pushups: { label: pushupsLabel, prescription: pushupsPrescription },
    squats: { label: 'Squats', prescription: `3 × ${squatTarget}` },
    plank: { label: 'Plank', prescription: `${nextPlankSeconds} sec × 3` },
    lunges: { label: 'Lunges', prescription: '3 × 10 each leg' },
    cardio: { label: 'Cardio', prescription: `${cardioTarget} min` },
  }
}

export function buildWeeklySummary(dailyLogs) {
  const recentEntries = Object.entries(dailyLogs)
    .map(([dateKey, log]) => normalizeDailyLog(log, dateKey))
    .sort((a, b) => a.date.localeCompare(b.date))
    .slice(-7)

  return {
    checkIns: recentEntries.length,
    workoutsCompleted: recentEntries.filter((entry) => getCompletedExerciseCount(entry) === 5).length,
    dietHits: recentEntries.filter((entry) => entry.dietFollowed === 'yes').length,
  }
}

export function buildCoachInsights(profile, dailyLogs, weightMetrics) {
  const recentEntries = Object.entries(dailyLogs)
    .map(([dateKey, log]) => normalizeDailyLog(log, dateKey))
    .sort((a, b) => a.date.localeCompare(b.date))
    .slice(-7)

  const workoutTemplate = buildWorkoutTemplate(profile, recentEntries, weightMetrics)
  const workoutsCompleted = recentEntries.filter((entry) => getCompletedExerciseCount(entry) === 5).length
  const lowStrength = profile.fitnessLevel === 'beginner' && workoutsCompleted <= 2
  const weightNotDropping = weightMetrics.sevenDayStatus === 'Adjust diet' || weightMetrics.sevenDayStatus === "You're overeating"
  const streakHigh = weightMetrics.streakCount >= 5

  let adviceMessage = weightMetrics.sevenDayStatus === 'Need more data' ? "You're on track" : weightMetrics.sevenDayStatus
  const recommendations = ['Keep protein high and keep today simple.']

  if (lowStrength) {
    adviceMessage = 'Use the easier version and focus on perfect form.'
    recommendations[0] = 'Open with incline pushups and smooth tempo to build consistency.'
  }

  if (weightNotDropping) {
    adviceMessage = 'Reduce carbs slightly.'
    recommendations.push('Add 5 extra cardio minutes and tighten portions at your next meals.')
  }

  if (streakHigh) {
    adviceMessage = 'Increase intensity today.'
    recommendations.push('Your streak is strong—push the final set or add one extra round.')
  }

  return {
    adviceMessage,
    recommendations,
    lowStrength,
    weightNotDropping,
    streakHigh,
    dailyWorkoutPlan: workoutTemplate,
    readablePlan: `Today’s Plan:\n- ${workoutTemplate.pushups.label}: ${workoutTemplate.pushups.prescription}\n- Squats: ${workoutTemplate.squats.prescription}\n- Plank: ${workoutTemplate.plank.prescription}\n- Lunges: ${workoutTemplate.lunges.prescription}\n- Cardio: ${workoutTemplate.cardio.prescription}`,
  }
}

export function buildAlerts(dailyLogs, weightMetrics) {
  const sortedDates = Object.keys(dailyLogs).sort()
  const latestDate = sortedDates.at(-1) ?? null
  const alerts = []

  if (!latestDate) return alerts

  const latestTimestamp = new Date(`${latestDate}T00:00:00Z`).getTime()
  const todayTimestamp = new Date(`${TODAY_LOG_KEY}T00:00:00Z`).getTime()
  const daysSinceLastEntry = Math.floor((todayTimestamp - latestTimestamp) / DAY_IN_MS)

  if (daysSinceLastEntry >= 2) {
    alerts.push({ type: 'warning', title: 'No entry for 2 days', message: 'Log today to restore your trend and coaching updates.' })
  }

  if (weightMetrics.streakCount <= 1 && sortedDates.length > 1 && daysSinceLastEntry >= 1) {
    alerts.push({ type: 'alert', title: 'Streak broken', message: "Your logging streak broke. Restart with today’s check-in." })
  }

  return alerts
}
