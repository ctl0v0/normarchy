import QtQuick
import QtTest
import "../Model.js" as Model

TestCase {
  name: "NormBreakModel"

  function item(id, duration) {
    return {
      id: id,
      duration_seconds: duration,
      enabled: true
    }
  }

  function test_durationBuckets() {
    compare(Model.eligible(item("quick", 179), Model.MODE_QUICK), true)
    compare(Model.eligible(item("classic-start", 180), Model.MODE_CLASSIC), true)
    compare(Model.eligible(item("classic-end", 899), Model.MODE_CLASSIC), true)
    compare(Model.eligible(item("long", 900), Model.MODE_LONG), true)
    compare(Model.eligible(item("unknown", null), Model.MODE_QUICK), false)
    compare(Model.eligible(item("unknown", null), Model.MODE_ANYTHING), true)
  }

  function test_disabledItemsAreExcluded() {
    var disabled = item("disabled", 30)
    disabled.enabled = false
    compare(Model.eligible(disabled, Model.MODE_ANYTHING), false)
  }

  function test_recentHistoryIsAvoided() {
    var items = [item("a", 20), item("b", 30), item("c", 40)]
    var queue = Model.buildQueue(items, Model.MODE_QUICK, ["a", "b"], function() { return 0 })
    compare(queue.length, 1)
    compare(queue[0].id, "c")
  }

  function test_historyFallsBackWhenEverythingIsRecent() {
    var items = [item("a", 20), item("b", 30)]
    var queue = Model.buildQueue(items, Model.MODE_QUICK, ["a", "b"], function() { return 0 })
    compare(queue.length, 2)
    verify(queue[0].id !== queue[1].id)
  }

  function test_durationFormatting() {
    compare(Model.formatDuration(71), "1:11")
    compare(Model.formatDuration(3661), "1:01:01")
  }
}
