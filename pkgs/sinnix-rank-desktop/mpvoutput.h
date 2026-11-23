#pragma once

#include <QQuickFramebufferObject>
#include <QUrl>
#include <QtQml/qqmlregistration.h>
#include <memory>
#include <optional>

struct Mpv;

class MpvOutput : public QQuickFramebufferObject {
    Q_OBJECT
    QML_ELEMENT
    Q_PROPERTY(QUrl source READ source WRITE setSource NOTIFY sourceChanged)
    Q_PROPERTY(qint64 position READ position NOTIFY positionChanged)
    Q_PROPERTY(qint64 duration READ duration NOTIFY durationChanged)
    Q_PROPERTY(bool playing READ playing NOTIFY playingChanged)
    Q_PROPERTY(QString playbackError READ playbackError NOTIFY playbackErrorChanged)
    Q_PROPERTY(bool stretch READ stretch WRITE setStretch NOTIFY stretchChanged)
    Q_PROPERTY(QSize renderSize READ renderSize WRITE setRenderSize NOTIFY renderSizeChanged)
    Q_PROPERTY(qreal volume READ volume WRITE setVolume NOTIFY volumeChanged)
    Q_PROPERTY(bool muted READ muted WRITE setMuted NOTIFY mutedChanged)
    Q_PROPERTY(QString hardwareDecoder READ hardwareDecoder NOTIFY hardwareDecoderChanged)

public:
    explicit MpvOutput(QQuickItem *parent = nullptr);
    ~MpvOutput() override;
    Renderer *createRenderer() const override;

    QUrl source() const { return m_source; }
    qint64 position() const { return m_position; }
    qint64 duration() const { return m_duration; }
    bool playing() const { return m_playing; }
    QString playbackError() const { return m_error; }
    bool stretch() const { return m_stretch; }
    QSize renderSize() const { return m_renderSize; }
    qreal volume() const { return m_volume; }
    bool muted() const { return m_muted; }
    QString hardwareDecoder() const { return m_hardwareDecoder; }

    void setSource(const QUrl &value);
    void setStretch(bool value);
    void setRenderSize(const QSize &value);
    void setVolume(qreal value);
    void setMuted(bool value);

    Q_INVOKABLE void play();
    Q_INVOKABLE void pause();
    Q_INVOKABLE void stop();
    // A scrub jumps to the nearest keyframe so pointer-driven seeking keeps up
    // with 8K sources; an exact seek decodes to the requested frame.
    Q_INVOKABLE void seek(qreal milliseconds, bool exact = true);

signals:
    void sourceChanged();
    void positionChanged();
    void durationChanged();
    void playingChanged();
    void playbackErrorChanged();
    void stretchChanged();
    void renderSizeChanged();
    void volumeChanged();
    void mutedChanged();
    void hardwareDecoderChanged();

private:
    void drainEvents();
    void applyPlayback();
    void applySeek();
    void setPosition(qint64 value);
    void setDuration(qint64 value);
    void setPlaying(bool value);
    void setError(const QString &value);

    std::shared_ptr<Mpv> m_mpv;
    QUrl m_source;
    QString m_path;
    QSize m_renderSize;
    qint64 m_position = 0;
    qint64 m_duration = 0;
    qreal m_volume = 1;
    bool m_muted = true;
    bool m_stretch = false;
    bool m_renderReady = false;
    bool m_open = false;
    bool m_loaded = false;
    bool m_requestedPlay = false;
    bool m_playing = false;
    bool m_eof = false;
    std::optional<qreal> m_pendingSeek;
    bool m_pendingExact = true;
    QString m_error;
    QString m_hardwareDecoder;
};
