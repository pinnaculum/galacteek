from PyQt5.QtMultimedia import QSound

from galacteek.config import cGet


def playSound(name: str) -> None:
    QSound.play(':/share/static/sounds/{fn}'.format(
        fn=name if name.endswith('.wav') else f'{name}.wav'
    ))


def uiNotify(notificationName: str) -> None:
    notification = cGet(f'notifications.{notificationName}',
                        mod='galacteek.ui')

    if not notification:
        return

    sound = notification.get('sound')
    if isinstance(sound, str):
        playSound(sound)
