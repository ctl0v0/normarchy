import QtQuick
import QtMultimedia
import Quickshell.Io
import "Model.js" as Model

Item {
  id: root

  property var settings: ({})
  property var catalogItems: []
  property int catalogVersion: 0
  property bool catalogLoaded: false

  property string activeMode: Model.MODE_QUICK
  property var queue: []
  property string queueMode: ""
  property var recentIds: []
  property var quarantine: ({})

  property bool sessionActive: false
  property string sessionOwner: ""
  property bool loading: false
  property bool streamReady: false
  property bool pendingStart: false
  property bool expectedStop: false
  property bool failureInProgress: false
  property bool userPaused: false
  property int attemptCount: 0

  property var currentItem: null
  property string mediaUrl: ""
  property int mediaWidth: 0
  property int mediaHeight: 0
  property int mediaDuration: 0
  property string statusText: ""
  property string errorText: ""
  property bool playbackEnded: false

  readonly property bool playing: mediaPlayer.playbackState === MediaPlayer.PlayingState
  readonly property bool muted: audioOutput.muted
  readonly property int playbackPosition: mediaPlayer.position
  readonly property int playbackDuration: mediaPlayer.duration

  readonly property string thumbnailUrl: currentItem
    ? "https://i.ytimg.com/vi/" + currentItem.id + "/hqdefault.jpg"
    : ""
  readonly property string catalogPath: String(Qt.resolvedUrl("catalog/norm-clips.json"))
  readonly property string proxyPath: decodeURIComponent(
    String(Qt.resolvedUrl("scripts/stream_proxy.py")).replace(/^file:\/\//, ""))

  function startSession(owner, mode) {
    sessionOwner = String(owner || "")
    sessionActive = true
    requestNext(mode, false)
  }

  function stopPlayback() {
    sessionActive = false
    sessionOwner = ""
    pendingStart = false
    loading = false
    streamReady = false
    failureInProgress = false
    userPaused = false
    statusText = ""
    errorText = ""
    mediaUrl = ""
    playbackEnded = false
    mediaPlayer.stop()
    mediaPlayer.source = ""
    resolverTimer.stop()
    retryTimer.stop()
    if (streamProcess.running) {
      expectedStop = true
      streamProcess.running = false
    }
  }

  function requestNext(mode, automatic) {
    activeMode = Model.normalizeMode(mode)
    sessionActive = true
    if (!automatic) attemptCount = 0
    pendingStart = true
    failureInProgress = false
    userPaused = false
    loading = true
    streamReady = false
    mediaUrl = ""
    playbackEnded = false
    mediaPlayer.stop()
    mediaPlayer.source = ""
    errorText = ""
    statusText = automatic
      ? "That one wandered off. Trying another..."
      : "Finding an old chunk of coal..."

    if (!catalogLoaded) {
      catalogFile.reload()
      return
    }
    if (streamProcess.running) {
      expectedStop = true
      streamProcess.running = false
    } else {
      Qt.callLater(root._selectAndStart)
    }
  }

  function _selectAndStart() {
    if (!sessionActive || !pendingStart || !catalogLoaded) return
    pendingStart = false
    failureInProgress = false

    var selected = null
    var remaining = catalogItems.length + 1
    while (remaining > 0 && selected === null) {
      if (queueMode !== activeMode || queue.length === 0) {
        queue = Model.buildQueue(catalogItems, activeMode, recentIds)
        queueMode = activeMode
      }
      if (queue.length === 0) break
      var candidate = queue.shift()
      var quarantinedUntil = Number(quarantine[String(candidate.id)] || 0)
      if (quarantinedUntil <= Date.now()) selected = candidate
      remaining--
    }

    if (selected === null) {
      loading = false
      errorText = "No playable clips are available in this length right now."
      statusText = ""
      return
    }

    currentItem = selected
    recentIds = recentIds.concat([String(selected.id)]).slice(-12)
    mediaWidth = Number(selected.width || 0)
    mediaHeight = Number(selected.height || 0)
    mediaDuration = Number(selected.duration_seconds || 0)
    streamReady = false
    mediaUrl = ""
    mediaPlayer.stop()
    mediaPlayer.source = ""
    expectedStop = false

    streamProcess.command = ["python3", proxyPath, selected.url]
    streamProcess.running = true
    resolverTimer.restart()
  }

  function _shortError(message) {
    var text = String(message || "").replace(/^\s+|\s+$/g, "")
    if (text.length > 180) text = text.substring(0, 177) + "..."
    return text
  }

  function _handleFailure(message) {
    if (!sessionActive || failureInProgress) return
    failureInProgress = true
    resolverTimer.stop()
    streamReady = false
    mediaUrl = ""
    if (currentItem) {
      var nextQuarantine = ({})
      for (var key in quarantine) nextQuarantine[key] = quarantine[key]
      nextQuarantine[String(currentItem.id)] = Date.now() + 30 * 60 * 1000
      quarantine = nextQuarantine
    }

    attemptCount++
    if (attemptCount >= 6) {
      pendingStart = false
      loading = false
      statusText = ""
      errorText = _shortError(message) || "Several clips failed to load."
    } else {
      pendingStart = true
      loading = true
      statusText = "That one wandered off. Trying another..."
      errorText = ""
    }

    if (streamProcess.running) {
      expectedStop = true
      streamProcess.running = false
    } else if (pendingStart) {
      retryTimer.restart()
    }
  }

  function playbackFailed(message) {
    _handleFailure(message || "Playback failed")
  }

  function handleProxyLine(line) {
    if (!sessionActive || !currentItem) return
    var payload
    try {
      payload = JSON.parse(String(line || ""))
    } catch (_error) {
      return
    }
    if (payload.status !== "ready" || String(payload.id) !== String(currentItem.id)) return
    resolverTimer.stop()
    mediaWidth = Number(payload.width || mediaWidth)
    mediaHeight = Number(payload.height || mediaHeight)
    mediaDuration = Number(payload.duration || mediaDuration)
    mediaUrl = String(payload.url || "")
    streamReady = mediaUrl !== ""
    loading = !streamReady
    statusText = ""
    if (streamReady) {
      mediaPlayer.source = mediaUrl
      var expectedUrl = mediaUrl
      Qt.callLater(function() {
        if (root.sessionActive && root.mediaUrl === expectedUrl) mediaPlayer.play()
      })
    }
  }

  function attachVideo(output) {
    if (!output || mediaPlayer.videoOutput === output) return
    var shouldResume = playing
    mediaPlayer.videoOutput = output
    if (shouldResume) Qt.callLater(function() {
      if (root.sessionActive) mediaPlayer.play()
    })
  }

  function detachVideo(output) {
    if (mediaPlayer.videoOutput !== output) return
    var shouldResume = playing
    mediaPlayer.videoOutput = backgroundVideoOutput
    if (shouldResume) Qt.callLater(function() {
      if (root.sessionActive) mediaPlayer.play()
    })
  }

  function togglePlayback() {
    if (!sessionActive || mediaPlayer.source === "") return
    if (playing) {
      userPaused = true
      mediaPlayer.pause()
    } else {
      userPaused = false
      mediaPlayer.play()
    }
  }

  function toggleMuted() {
    audioOutput.muted = !audioOutput.muted
  }

  function replay() {
    if (mediaPlayer.source === "") return
    userPaused = false
    playbackEnded = false
    mediaPlayer.position = 0
    mediaPlayer.play()
  }

  AudioOutput {
    id: audioOutput
    volume: 0.82
    muted: false
  }

  VideoOutput {
    id: backgroundVideoOutput
    visible: false
  }

  MediaPlayer {
    id: mediaPlayer
    audioOutput: audioOutput
    videoOutput: backgroundVideoOutput

    onMediaStatusChanged: {
      if (mediaStatus === MediaPlayer.EndOfMedia) root.playbackEnded = true
      else if (root.sessionActive && !root.playbackEnded
          && (mediaStatus === MediaPlayer.LoadedMedia || mediaStatus === MediaPlayer.BufferedMedia)) {
        mediaPlayer.play()
      }
    }
    onErrorOccurred: function(_error, errorString) {
      if (root.sessionActive) root._handleFailure(errorString || "Playback failed")
    }
  }

  FileView {
    id: catalogFile
    path: root.catalogPath
    printErrors: false
    onLoaded: {
      try {
        var catalog = JSON.parse(text())
        root.catalogItems = Array.isArray(catalog.items) ? catalog.items : []
        root.catalogVersion = Number(catalog.catalog_version || 0)
        root.catalogLoaded = root.catalogItems.length > 0
        if (!root.catalogLoaded) throw new Error("Catalog is empty")
        if (root.pendingStart) Qt.callLater(root._selectAndStart)
      } catch (error) {
        root.catalogLoaded = false
        root.loading = false
        root.errorText = "The Norm catalog could not be read."
        console.warn("Normarchy catalog error:", error)
      }
    }
    onLoadFailed: {
      root.catalogLoaded = false
      root.loading = false
      root.errorText = "The Norm catalog is missing."
    }
  }

  Process {
    id: streamProcess
    running: false
    command: []
    stdout: SplitParser {
      onRead: function(line) { root.handleProxyLine(line) }
    }
    stderr: StdioCollector {
      id: proxyError
      waitForEnd: true
    }
    onExited: function(exitCode) {
      resolverTimer.stop()
      if (root.expectedStop) {
        root.expectedStop = false
        if (root.pendingStart && root.sessionActive) Qt.callLater(root._selectAndStart)
        return
      }
      if (!root.sessionActive) return
      var message = proxyError.text || (exitCode === 0
        ? "The local stream ended unexpectedly."
        : "YouTube could not prepare this clip.")
      root._handleFailure(message)
    }
  }

  Timer {
    id: resolverTimer
    interval: 25000
    repeat: false
    onTriggered: root._handleFailure("YouTube took too long to prepare this clip.")
  }

  Timer {
    id: retryTimer
    interval: 250
    repeat: false
    onTriggered: root._selectAndStart()
  }

  Timer {
    interval: 1000
    repeat: true
    running: root.sessionActive && root.streamReady && !root.playbackEnded && !root.userPaused
    onTriggered: if (!root.playing && mediaPlayer.source !== "") mediaPlayer.play()
  }

  IpcHandler {
    target: "normarchy"

    function status(): string {
      return JSON.stringify({
        sessionActive: root.sessionActive,
        sessionOwner: root.sessionOwner,
        catalogLoaded: root.catalogLoaded,
        mode: root.activeMode,
        loading: root.loading,
        streamReady: root.streamReady,
        playing: root.playing,
        userPaused: root.userPaused,
        processRunning: streamProcess.running,
        currentId: root.currentItem ? root.currentItem.id : "",
        position: root.playbackPosition,
        duration: root.playbackDuration,
        error: root.errorText
      })
    }

    function next(): string {
      root.requestNext(root.activeMode, false)
      return "ok"
    }

    function stop(): string {
      root.stopPlayback()
      return "ok"
    }
  }

  Component.onCompleted: catalogFile.reload()
}
