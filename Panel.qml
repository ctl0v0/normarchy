pragma ComponentBehavior: Bound

import QtQuick
import QtMultimedia
import Quickshell
import qs.Commons
import qs.Ui
import "Model.js" as Model

Panel {
  id: root

  moduleName: "io.github.ctl0v0.normarchy"
  manageIpc: false

  readonly property var normService: bar && bar.shell ? bar.shell.serviceFor(moduleName) : null
  readonly property color foreground: bar ? bar.foreground : Color.foreground
  readonly property color dim: Qt.darker(foreground, 1.55)
  readonly property string fontFamily: bar ? bar.fontFamily : Style.font.family
  readonly property string sessionToken: moduleName + ":" + Math.random().toString(36).substring(2)
  property string selectedMode: Model.MODE_QUICK

  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  function mergeSetting(key, value) {
    var next = ({})
    for (var existing in settings) next[existing] = settings[existing]
    next[key] = value
    return next
  }

  function saveMode(value) {
    selectedMode = Model.normalizeMode(value)
    if (bar && bar.shell) bar.shell.updateEntryInline(moduleName, mergeSetting("lengthMode", selectedMode))
    if (opened && normService) normService.requestNext(selectedMode, false)
  }

  function anotherNorm() {
    if (normService) normService.requestNext(selectedMode, false)
  }

  function togglePlayer() {
    if (normService) normService.togglePlayback()
  }

  function toggleMuted() {
    if (normService) normService.toggleMuted()
  }

  function replay() {
    if (normService) normService.replay()
  }

  function stopPlayback() {
    if (normService) normService.stopPlayback()
  }

  function openOriginal() {
    if (!normService || !normService.currentItem) return
    Quickshell.execDetached(["omarchy-launch-browser", normService.currentItem.url])
  }

  function categoryLabel(category) {
    var text = String(category || "Norm Macdonald").replace(/-/g, " ")
    return text.replace(/\b\w/g, function(letter) { return letter.toUpperCase() })
  }

  onSettingsChanged: selectedMode = Model.normalizeMode(setting("lengthMode", Model.MODE_QUICK))
  onOpenedChanged: {
    if (opened) {
      selectedMode = Model.normalizeMode(setting("lengthMode", Model.MODE_QUICK))
      if (normService) {
        normService.attachVideo(videoOutput)
        if (!normService.sessionActive) normService.startSession(sessionToken, selectedMode)
      }
      Qt.callLater(function() { keyCatcher.forceActiveFocus() })
    } else if (normService) {
      normService.detachVideo(videoOutput)
    }
  }

  Binding {
    target: root.normService
    property: "settings"
    value: root.settings
    when: root.normService !== null
  }

  WidgetButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    hasVisualContent: true
    labelVisible: false
    fixedWidth: vertical ? -1 : Style.space(52)
    fixedHeight: vertical ? Style.space(52) : -1
    active: root.opened || (root.normService && root.normService.sessionActive)
    tooltipText: root.normService && root.normService.sessionActive
      ? "Normarchy - Playing"
      : "Normarchy"

    NormWordmark {
      anchors.centerIn: parent
      width: Style.space(48)
      height: Style.space(16)
      rotation: button.vertical ? -90 : 0
      color: button.active && button.useActiveColor ? button.activeColor : button.foreground
      fontFamily: root.fontFamily
    }

    onPressed: function(buttonCode) {
      if (buttonCode === Qt.LeftButton) root.toggle()
      else if (buttonCode === Qt.MiddleButton) root.stopPlayback()
    }
  }

  StickyKeyboardPanel {
    id: panel
    anchorItem: button
    owner: root
    bar: root.bar
    open: root.opened
    focusTarget: keyCatcher
    contentWidth: panel.fittedContentWidth(Style.space(460))
    contentHeight: panel.fittedContentHeight(content.implicitHeight, Style.space(720))

    PanelKeyCatcher {
      id: keyCatcher
      anchors.fill: parent
      blocked: modePicker.popupOpen
      onActivateRequested: root.togglePlayer()
      onMoveRequested: function(dx, _dy) {
        if (dx > 0) root.anotherNorm()
      }
      onCloseRequested: root.close()
      onTabRequested: function(direction) { root.switchPanel(direction) }
      onTextKey: function(text) {
        var key = String(text).toLowerCase()
        if (key === "n") root.anotherNorm()
        else if (key === "m") root.toggleMuted()
        else if (key === "o") root.openOriginal()
        else if (key === "r") root.replay()
        else if (key === "s") root.stopPlayback()
      }

      Column {
        id: content
        width: parent.width
        spacing: Style.space(10)

        Row {
          width: parent.width
          spacing: Style.space(10)

          Column {
            width: parent.width - modePicker.width - parent.spacing
            spacing: Style.space(2)

            Text {
              width: parent.width
              text: "NORMARCHY"
              color: root.dim
              font.family: root.fontFamily
              font.pixelSize: Style.font.caption
              font.bold: true
              font.letterSpacing: Style.space(1)
            }

            Text {
              width: parent.width
              text: root.normService && root.normService.currentItem
                ? root.normService.currentItem.title
                : "A little Norm between things"
              color: root.foreground
              font.family: root.fontFamily
              font.pixelSize: Style.font.subtitle
              font.bold: true
              elide: Text.ElideRight
              textFormat: Text.PlainText
            }
          }

          Dropdown {
            id: modePicker
            width: Style.space(164)
            showLabel: false
            value: root.selectedMode
            foreground: root.foreground
            fontFamily: root.fontFamily
            options: [
              { value: Model.MODE_QUICK, label: "Quick  < 3 min" },
              { value: Model.MODE_CLASSIC, label: "Classic  3-15 min" },
              { value: Model.MODE_LONG, label: "Long  15+ min" },
              { value: Model.MODE_ANYTHING, label: "Anything" }
            ]
            onChanged: function(value) { root.saveMode(value) }
          }
        }

        BorderSurface {
          id: videoFrame
          width: parent.width
          height: {
            var vertical = root.normService
              && root.normService.mediaHeight > root.normService.mediaWidth
            return vertical ? Style.space(400) : Math.round(width * 9 / 16)
          }
          radius: Math.min(Style.cornerRadius, Style.space(8))
          color: "#080808"
          borderSpec: Border.controlSpec("normal", root.foreground, Color.accent)
          clip: true

          Image {
            anchors.fill: parent
            anchors.margins: videoFrame.borderLeft
            source: root.normService ? root.normService.thumbnailUrl : ""
            fillMode: Image.PreserveAspectFit
            asynchronous: true
            cache: true
            opacity: root.normService && root.normService.streamReady ? 0 : 0.58
            visible: source !== ""

            Behavior on opacity { NumberAnimation { duration: 120 } }
          }

          VideoOutput {
            id: videoOutput
            anchors.fill: parent
            anchors.margins: videoFrame.borderLeft
            fillMode: VideoOutput.PreserveAspectFit
            visible: root.normService && root.normService.streamReady
          }

          Rectangle {
            anchors.fill: parent
            color: "#99000000"
            visible: root.normService
              && (!root.normService.sessionActive
                || root.normService.loading
                || root.normService.errorText !== ""
                || root.normService.playbackEnded)

            Column {
              anchors.centerIn: parent
              width: Math.min(parent.width - Style.space(36), Style.space(320))
              spacing: Style.space(10)

              Text {
                anchors.horizontalCenter: parent.horizontalCenter
                width: parent.width
                text: root.normService && root.normService.errorText !== ""
                  ? root.normService.errorText
                  : (root.normService && root.normService.playbackEnded
                    ? "That's the end of that one."
                    : (root.normService && !root.normService.sessionActive
                      ? "Normarchy is stopped."
                      : (root.normService ? root.normService.statusText : "")))
                color: "white"
                font.family: root.fontFamily
                font.pixelSize: Style.font.body
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WordWrap
                textFormat: Text.PlainText
              }

              Button {
                anchors.horizontalCenter: parent.horizontalCenter
                visible: root.normService
                  && (!root.normService.sessionActive
                    || root.normService.playbackEnded
                    || root.normService.errorText !== "")
                text: root.normService && !root.normService.sessionActive
                  ? "Start Normarchy"
                  : (root.normService && root.normService.playbackEnded ? "Another Norm" : "Try again")
                iconText: "󰒭"
                foreground: "white"
                bordered: true
                focusable: true
                onClicked: root.anotherNorm()
              }
            }
          }

          Rectangle {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            anchors.leftMargin: videoFrame.borderLeft
            anchors.rightMargin: videoFrame.borderRight
            anchors.bottomMargin: videoFrame.borderBottom
            height: Style.space(3)
            color: "#44ffffff"
            visible: root.normService && root.normService.playbackDuration > 0

            Rectangle {
              width: parent.width * Math.max(0, Math.min(1,
                root.normService
                  ? root.normService.playbackPosition / Math.max(1, root.normService.playbackDuration)
                  : 0))
              height: parent.height
              color: Color.accent
            }
          }
        }

        Row {
          width: parent.width
          spacing: Style.space(8)

          Text {
            width: parent.width - durationText.width - parent.spacing
            text: root.normService && root.normService.currentItem
              ? root.categoryLabel(root.normService.currentItem.category)
                + "  /  " + String(root.normService.currentItem.source_tier || "archive").toUpperCase()
              : ""
            color: root.dim
            font.family: root.fontFamily
            font.pixelSize: Style.font.caption
            elide: Text.ElideRight
            textFormat: Text.PlainText
          }

          Text {
            id: durationText
            text: root.normService ? Model.formatDuration(root.normService.mediaDuration) : ""
            color: root.dim
            font.family: root.fontFamily
            font.pixelSize: Style.font.caption
          }
        }

        Row {
          anchors.horizontalCenter: parent.horizontalCenter
          spacing: Style.space(6)

          Button {
            iconText: root.normService && root.normService.playing ? "󰏤" : "󰐊"
            tooltipText: root.normService && root.normService.playing ? "Pause (Space)" : "Play (Space)"
            foreground: root.foreground
            focusable: true
            enabled: root.normService && root.normService.streamReady
            onClicked: root.togglePlayer()
          }

          Button {
            text: "Another Norm"
            iconText: "󰒭"
            tooltipText: "Another Norm (N or Right Arrow)"
            foreground: root.foreground
            bordered: true
            selected: true
            focusable: true
            onClicked: root.anotherNorm()
          }

          Button {
            iconText: root.normService && root.normService.muted ? "󰝟" : "󰕾"
            tooltipText: "Mute (M)"
            foreground: root.foreground
            focusable: true
            enabled: root.normService && root.normService.streamReady
            onClicked: root.toggleMuted()
          }

          Button {
            iconText: "󰓛"
            tooltipText: "Stop Normarchy"
            foreground: root.foreground
            focusable: true
            enabled: root.normService && root.normService.sessionActive
            onClicked: root.stopPlayback()
          }

          Button {
            iconText: "󰖟"
            tooltipText: "Open original on YouTube (O)"
            foreground: root.foreground
            focusable: true
            enabled: root.normService && root.normService.currentItem !== null
            onClicked: root.openOriginal()
          }
        }

        Text {
          anchors.horizontalCenter: parent.horizontalCenter
          text: "SPACE play/pause   N next   M mute   S stop   ESC close"
          color: root.dim
          font.family: root.fontFamily
          font.pixelSize: Style.font.caption
          horizontalAlignment: Text.AlignHCenter
        }
      }
    }
  }

  Component.onCompleted: selectedMode = Model.normalizeMode(setting("lengthMode", Model.MODE_QUICK))
  Component.onDestruction: if (normService) normService.detachVideo(videoOutput)
}
