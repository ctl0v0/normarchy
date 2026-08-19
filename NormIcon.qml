import QtQuick

Item {
  id: root

  property color color: "white"

  Canvas {
    id: canvas
    anchors.fill: parent
    antialiasing: true

    onPaint: {
      var context = getContext("2d")
      context.reset()
      context.scale(width / 32, height / 32)
      context.fillStyle = root.color

      // A solid posterized portrait keeps the face readable at bar size.
      context.beginPath()
      context.moveTo(4.4, 14.7)
      context.bezierCurveTo(3.8, 10, 5.1, 6.5, 8.3, 4.3)
      context.bezierCurveTo(10, 2.8, 12.2, 2.8, 13.7, 2.2)
      context.bezierCurveTo(16.9, 0.6, 21.4, 1.4, 23.4, 3.6)
      context.bezierCurveTo(27.1, 4.6, 28.5, 8.6, 27.9, 12.2)
      context.bezierCurveTo(29, 14.1, 28.5, 17.1, 26.8, 18.7)
      context.bezierCurveTo(26, 24.4, 22.2, 29.4, 17.2, 30.3)
      context.bezierCurveTo(12.4, 30, 8.3, 26.4, 7.1, 21.6)
      context.bezierCurveTo(4.4, 20.2, 3.5, 17.1, 4.4, 14.7)
      context.closePath()
      context.fill()

      context.globalCompositeOperation = "destination-out"
      context.fillStyle = "black"
      context.strokeStyle = "black"
      context.lineCap = "round"
      context.lineJoin = "round"

      // Hairline, brows, and narrowed eyes.
      context.lineWidth = 1.1
      context.beginPath()
      context.moveTo(6.3, 10.8)
      context.bezierCurveTo(10.2, 7.4, 20.8, 6.7, 26, 10.4)
      context.stroke()

      context.beginPath()
      context.moveTo(7.8, 14.2)
      context.bezierCurveTo(9.8, 13.1, 12.7, 13.4, 14, 14.8)
      context.bezierCurveTo(11.4, 14.2, 9.4, 15.4, 7.6, 15.2)
      context.closePath()
      context.fill()

      context.beginPath()
      context.moveTo(17.4, 14.8)
      context.bezierCurveTo(19.2, 13.3, 22.7, 13, 24.8, 14.1)
      context.lineTo(24.5, 15.2)
      context.bezierCurveTo(22.1, 14.5, 19.7, 14.6, 17.4, 15.8)
      context.closePath()
      context.fill()

      // Broad nose and asymmetrical smile.
      context.beginPath()
      context.moveTo(16.2, 14.7)
      context.bezierCurveTo(15.9, 17.8, 14.8, 19.9, 13.7, 21.4)
      context.bezierCurveTo(15.3, 20.9, 16.5, 21.5, 17.4, 22)
      context.bezierCurveTo(18.6, 21.7, 19.2, 20.8, 19.5, 19.8)
      context.bezierCurveTo(18.2, 20.3, 17.5, 19, 17.3, 15.5)
      context.closePath()
      context.fill()

      context.lineWidth = 1.45
      context.beginPath()
      context.moveTo(10, 23)
      context.bezierCurveTo(13.1, 25.3, 18.8, 26, 22.4, 22.9)
      context.bezierCurveTo(18.6, 24.3, 14.4, 24.1, 10, 23)
      context.stroke()

      context.lineWidth = 0.85
      context.beginPath()
      context.moveTo(12.1, 25.1)
      context.bezierCurveTo(14.6, 27, 18, 27.3, 20.4, 25.4)
      context.moveTo(7.1, 18.8)
      context.bezierCurveTo(6.2, 20.3, 6.4, 22.1, 7.8, 23.1)
      context.moveTo(24.8, 17.8)
      context.bezierCurveTo(25.7, 20.9, 24.2, 25.3, 21.4, 27.4)
      context.stroke()

      context.globalCompositeOperation = "source-over"
    }
  }

  onColorChanged: canvas.requestPaint()
  onWidthChanged: canvas.requestPaint()
  onHeightChanged: canvas.requestPaint()
}
