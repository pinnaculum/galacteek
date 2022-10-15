import QtQuick 2.2
import QtQuick.Controls 2.2
import QtGraphicalEffects 1.0
import QtQuick.Particles 2.0

import Galacteek 1.0

URLCloud {
  id: cloud
  anchors.fill: parent

  Rectangle {
    id: container
    anchors.fill: parent
    color: '#323232'

    property string currentUrl
    property string hoveredtUrl
    property color previousColor

    states: [
      State {
        name: 'colorchange'
        PropertyChanges { target: container; color: container.color }
      }
    ]

    Text {
      id: hoveredUrlText
      anchors.fill: parent
      font.family: 'Segoe UI'
      font.pointSize: 16
      color: 'lightblue'
    }

    Rectangle {
      id: rcenter
      anchors.centerIn: container
      width: 64
      height: 64
      radius: 32

      border.color: 'lightgray'
      border.width: 0

      Image {
        id: img
        anchors.centerIn: parent
        anchors.fill: parent
      }

      MouseArea {
        anchors.fill: rcenter
        hoverEnabled: true

        onClicked: {
          cloud.cloudClick()
        }

        onExited: {
          img.source = ''
        }

        onEntered: {
          img.source = 'qrc:/share/icons/helmets/ipfs-cosmo-black.png'

          emitter.burst(30)
        }
      }
    }

    transitions: [
      Transition {
        from: "*"; to: "*"

        SequentialAnimation {
          ColorAnimation {
            target: rcenter
            from: container.previousColor
            to: particle.color
            duration: 2000
            properties: "color"
          }
          ColorAnimation {
            target: rcenter
            from: particle.color
            to: '#323232'
            duration: 2000
            properties: "color"
          }
        }
      }
    ]

    ParticleSystem {
      id: particleSystem
    }

    Emitter {
      property int defaultEmitRate: 1
      property bool debug: false
      property int smallBurst: 10
      property int mediumBurst: 20

      id: emitter
      enabled: false
      width: container.width * 0.4
      height: container.height * 0.5
      anchors.centerIn: container
      system: particleSystem
      emitRate: defaultEmitRate
      lifeSpan: 800
      size: 16
      endSize: 64

      onEmitParticles: {
        if (particles.length > 0 && debug === true) {
          console.debug(
            container.currentUrl + ' EPC: ' + particles.length
          )
        }
      }
    }

    ImageParticle {
      id: particle
      source: 'qrc:/share/icons/particles/star.png'
      system: particleSystem
    }
  }

  Connections {
    target: cloud

    function onUrlChanged(cururl, urlcolor) {
      container.previousColor = container.color
      particle.color = urlcolor
      container.state = cururl
      container.currentUrl = cururl

      emitter.burst(emitter.mediumBurst)
    }

    function onUrlHovered(hovUrl, animate) {
      emitter.burst(emitter.smallBurst)
    }

    function onUrlAnimationStartStop(animate) {
      emitter.enabled = animate

      if (animate === true) {
        emitter.emitRate = emitter.defaultEmitRate
        emitter.burst(emitter.smallBurst)
      } else {
        emitter.emitRate = 0
      }
    }
  }
}
