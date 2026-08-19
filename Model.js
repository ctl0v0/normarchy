.pragma library

var MODE_QUICK = "Quick (< 3 min)"
var MODE_CLASSIC = "Classic (3-15 min)"
var MODE_LONG = "Long (15+ min)"
var MODE_ANYTHING = "Anything"

function modes() {
  return [MODE_QUICK, MODE_CLASSIC, MODE_LONG, MODE_ANYTHING]
}

function normalizeMode(value) {
  var candidate = String(value || "")
  return modes().indexOf(candidate) >= 0 ? candidate : MODE_QUICK
}

function eligible(item, mode) {
  if (!item || item.enabled !== true) return false
  var selected = normalizeMode(mode)
  if (selected === MODE_ANYTHING) return true

  var duration = Number(item.duration_seconds)
  if (!isFinite(duration) || duration <= 0) return false
  if (selected === MODE_QUICK) return duration < 180
  if (selected === MODE_CLASSIC) return duration >= 180 && duration < 900
  return duration >= 900
}

function shuffled(items, randomFunction) {
  var result = items.slice()
  var random = randomFunction || Math.random
  for (var i = result.length - 1; i > 0; i--) {
    var j = Math.floor(random() * (i + 1))
    var temporary = result[i]
    result[i] = result[j]
    result[j] = temporary
  }
  return result
}

function buildQueue(items, mode, recentIds, randomFunction) {
  var recent = ({})
  var history = recentIds || []
  for (var h = 0; h < history.length; h++) recent[String(history[h])] = true

  var eligibleItems = []
  var freshItems = []
  for (var i = 0; i < items.length; i++) {
    var item = items[i]
    if (!eligible(item, mode)) continue
    eligibleItems.push(item)
    if (!recent[String(item.id)]) freshItems.push(item)
  }

  return shuffled(freshItems.length > 0 ? freshItems : eligibleItems, randomFunction)
}

function formatDuration(seconds) {
  var total = Math.max(0, Math.round(Number(seconds) || 0))
  var hours = Math.floor(total / 3600)
  var minutes = Math.floor((total % 3600) / 60)
  var remainder = total % 60
  if (hours > 0)
    return hours + ":" + String(minutes).padStart(2, "0") + ":" + String(remainder).padStart(2, "0")
  return minutes + ":" + String(remainder).padStart(2, "0")
}
