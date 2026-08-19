import QtQuick

Item {
  id: root

  property color color: "white"
  property string fontFamily: "sans-serif"

  implicitWidth: 48
  implicitHeight: 16

  Row {
    anchors.centerIn: parent
    spacing: 1

    Text {
      anchors.verticalCenter: parent.verticalCenter
      text: "N"
      color: root.color
      font.family: root.fontFamily
      font.pixelSize: 12
      font.weight: Font.DemiBold
      font.letterSpacing: 0.5
      renderType: Text.NativeRendering
    }

    NormIcon {
      anchors.verticalCenter: parent.verticalCenter
      width: 14
      height: 14
      color: root.color
    }

    Text {
      anchors.verticalCenter: parent.verticalCenter
      text: "RM"
      color: root.color
      font.family: root.fontFamily
      font.pixelSize: 12
      font.weight: Font.DemiBold
      font.letterSpacing: 0.5
      renderType: Text.NativeRendering
    }
  }
}
