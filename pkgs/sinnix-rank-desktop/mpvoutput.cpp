#include "mpvoutput.h"

#include <QDir>
#include <QOpenGLContext>
#include <QOpenGLFramebufferObject>
#include <QQuickOpenGLUtils>
#include <mpv/client.h>
#include <mpv/render_gl.h>
#include <algorithm>
#include <cmath>

struct Mpv : QObject {
    Q_OBJECT

public:
    mpv_handle *handle = mpv_create();

    ~Mpv() {
        if (handle)
            mpv_terminate_destroy(handle);
    }

signals:
    void redraw();
    void eventsReady();
    void renderError(const QString &message);
};

class MpvRenderer : public QQuickFramebufferObject::Renderer {
public:
    explicit MpvRenderer(std::shared_ptr<Mpv> mpv) : m_mpv(std::move(mpv)) {}

    ~MpvRenderer() override {
        if (m_context) {
            mpv_render_context_set_update_callback(m_context, nullptr, nullptr);
            mpv_render_context_free(m_context);
        }
    }

    void synchronize(QQuickFramebufferObject *object) override {
        auto *item = static_cast<MpvOutput *>(object);
        if (m_size != item->renderSize()) {
            m_size = item->renderSize();
            invalidateFramebufferObject();
        }
    }

    QOpenGLFramebufferObject *createFramebufferObject(const QSize &size) override {
        return new QOpenGLFramebufferObject(m_size.isValid() ? m_size : size);
    }

    void render() override {
        if (!m_mpv)
            return;
        if (!m_context && (m_failed || !initialize()))
            return;

        auto *buffer = framebufferObject();
        mpv_opengl_fbo target = {int(buffer->handle()), buffer->width(), buffer->height(), 0};
        int flip = 1;
        int block = 0;
        mpv_render_param params[] = {
            {MPV_RENDER_PARAM_OPENGL_FBO, &target},
            {MPV_RENDER_PARAM_FLIP_Y, &flip},
            {MPV_RENDER_PARAM_BLOCK_FOR_TARGET_TIME, &block},
            {MPV_RENDER_PARAM_INVALID, nullptr},
        };
        mpv_render_context_update(m_context);
        mpv_render_context_render(m_context, params);
        QQuickOpenGLUtils::resetOpenGLState();
    }

private:
    bool initialize() {
        mpv_opengl_init_params gl = {
            [](void *, const char *name) -> void * {
                return reinterpret_cast<void *>(QOpenGLContext::currentContext()->getProcAddress(name));
            },
            nullptr,
        };
        mpv_render_param params[] = {
            {MPV_RENDER_PARAM_API_TYPE, const_cast<char *>(MPV_RENDER_API_TYPE_OPENGL)},
            {MPV_RENDER_PARAM_OPENGL_INIT_PARAMS, &gl},
            {MPV_RENDER_PARAM_INVALID, nullptr},
        };
        const int error = mpv_render_context_create(&m_context, m_mpv->handle, params);
        if (error < 0) {
            m_failed = true;
            emit m_mpv->renderError(QString::fromUtf8(mpv_error_string(error)));
            return false;
        }

        // Qt disconnects receiver signals when the item is destroyed. The
        // shared player survives until the render context is released too.
        mpv_render_context_set_update_callback(m_context, [](void *data) {
            emit static_cast<Mpv *>(data)->redraw();
        }, m_mpv.get());
        return true;
    }

    std::shared_ptr<Mpv> m_mpv;
    bool m_failed = false;
    mpv_render_context *m_context = nullptr;
    QSize m_size;
};

MpvOutput::MpvOutput(QQuickItem *parent)
    : QQuickFramebufferObject(parent),
      m_mpv(new Mpv(), [](Mpv *mpv) { mpv->deleteLater(); })
{
    setMirrorVertically(true);
    connect(m_mpv.get(), &Mpv::redraw, this, &MpvOutput::update, Qt::QueuedConnection);
    connect(m_mpv.get(), &Mpv::eventsReady, this, &MpvOutput::drainEvents, Qt::QueuedConnection);
    connect(m_mpv.get(), &Mpv::renderError, this, &MpvOutput::setError, Qt::QueuedConnection);
    auto *handle = m_mpv->handle;
    if (!handle) {
        m_mpv.reset();
        setError(QStringLiteral("Could not create the player"));
        return;
    }

    const std::pair<const char *, const char *> options[] = {
        {"config", "no"},
        {"load-scripts", "no"},
        {"vo", "libmpv"},
        {"hwdec", "auto-safe"},
        {"keep-open", "yes"},
        {"pause", "yes"},
        {"mute", "yes"},
        {"audio-display", "no"},
    };
    for (const auto &[name, value] : options)
        mpv_set_option_string(handle, name, value);
    const int error = mpv_initialize(handle);
    if (error < 0) {
        m_mpv.reset();
        setError(QString::fromUtf8(mpv_error_string(error)));
        return;
    }
    if (qEnvironmentVariableIsSet("SINNIX_RANK_MPV_LOG"))
        mpv_request_log_messages(handle, "debug");
    mpv_observe_property(handle, 0, "time-pos", MPV_FORMAT_DOUBLE);
    mpv_observe_property(handle, 0, "duration", MPV_FORMAT_DOUBLE);
    mpv_observe_property(handle, 0, "eof-reached", MPV_FORMAT_FLAG);
    mpv_observe_property(handle, 0, "hwdec-current", MPV_FORMAT_STRING);
    mpv_set_wakeup_callback(handle, [](void *data) {
        emit static_cast<Mpv *>(data)->eventsReady();
    }, m_mpv.get());
}

MpvOutput::~MpvOutput() {
    if (m_mpv)
        mpv_set_wakeup_callback(m_mpv->handle, nullptr, nullptr);
}

QQuickFramebufferObject::Renderer *MpvOutput::createRenderer() const {
    return new MpvRenderer(m_mpv);
}

void MpvOutput::setSource(const QUrl &value) {
    if (value == m_source)
        return;
    stop();
    m_source = value;
    m_path = value.isLocalFile() ? value.toLocalFile() : value.toString();
    if (!m_path.isEmpty() && (value.isLocalFile() || value.isRelative()))
        m_path = QDir::cleanPath(QDir::current().absoluteFilePath(m_path));
    if (m_mpv)
        setError({});
    emit sourceChanged();
}

void MpvOutput::setStretch(bool value) {
    if (value == m_stretch)
        return;
    m_stretch = value;
    if (m_mpv) {
        int keepAspect = !value;
        mpv_set_property_async(m_mpv->handle, 0, "keepaspect", MPV_FORMAT_FLAG, &keepAspect);
    }
    emit stretchChanged();
}

void MpvOutput::setRenderSize(const QSize &value) {
    if (value == m_renderSize)
        return;
    m_renderSize = value;
    update();
    emit renderSizeChanged();
}

void MpvOutput::setVolume(qreal value) {
    value = std::clamp(value, 0.0, 1.0);
    if (value == m_volume)
        return;
    m_volume = value;
    if (m_mpv) {
        double volume = value * 100;
        mpv_set_property_async(m_mpv->handle, 0, "volume", MPV_FORMAT_DOUBLE, &volume);
    }
    emit volumeChanged();
}

void MpvOutput::setMuted(bool value) {
    if (value == m_muted)
        return;
    m_muted = value;
    if (m_mpv) {
        int flag = value;
        mpv_set_property_async(m_mpv->handle, 0, "mute", MPV_FORMAT_FLAG, &flag);
    }
    emit mutedChanged();
}

void MpvOutput::play() {
    if (!m_mpv || m_path.isEmpty())
        return;
    m_requestedPlay = true;
    if (!m_open) {
        setError({});
        // Hold the first frame until a pending thumbnail seek is applied.
        int pause = 1;
        mpv_set_property_async(m_mpv->handle, 0, "pause", MPV_FORMAT_FLAG, &pause);
        const QByteArray path = m_path.toUtf8();
        const char *command[] = {"loadfile", path.constData(), "replace", nullptr};
        const int error = mpv_command_async(m_mpv->handle, 0, command);
        if (error < 0) {
            setError(QString::fromUtf8(mpv_error_string(error)));
            return;
        }
        m_open = true;
    }
    if (m_eof)
        seek(0);
    applyPlayback();
}

void MpvOutput::pause() {
    m_requestedPlay = false;
    applyPlayback();
}

void MpvOutput::stop() {
    if (m_open && m_mpv) {
        const char *command[] = {"stop", nullptr};
        mpv_command_async(m_mpv->handle, 0, command);
    }
    m_open = false;
    m_loaded = false;
    m_requestedPlay = false;
    m_eof = false;
    m_pendingSeek.reset();
    if (!m_hardwareDecoder.isEmpty()) {
        m_hardwareDecoder.clear();
        emit hardwareDecoderChanged();
    }
    setPlaying(false);
    setPosition(0);
    setDuration(0);
}

void MpvOutput::seek(qreal milliseconds) {
    if (!std::isfinite(milliseconds))
        return;
    m_pendingSeek = std::max<qreal>(0, milliseconds);
    applySeek();
}

void MpvOutput::applySeek() {
    if (!m_loaded || !m_pendingSeek || m_duration <= 0)
        return;
    const QByteArray seconds = QByteArray::number(std::min<qreal>(*m_pendingSeek, m_duration) / 1000);
    const char *command[] = {"seek", seconds.constData(), "absolute", nullptr};
    mpv_command_async(m_mpv->handle, 0, command);
    m_pendingSeek.reset();
}

void MpvOutput::applyPlayback() {
    if (!m_loaded)
        return;
    int pause = !m_requestedPlay;
    mpv_set_property_async(m_mpv->handle, 0, "pause", MPV_FORMAT_FLAG, &pause);
    setPlaying(m_requestedPlay);
}

void MpvOutput::drainEvents() {
    if (!m_mpv)
        return;
    auto *handle = m_mpv->handle;
    for (;;) {
        const auto *event = mpv_wait_event(handle, 0);
        if (event->event_id == MPV_EVENT_NONE)
            return;

        if (event->event_id == MPV_EVENT_LOG_MESSAGE) {
            const auto *message = static_cast<mpv_event_log_message *>(event->data);
            qInfo().noquote() << message->prefix << QString::fromUtf8(message->text).trimmed();
        } else if (event->event_id == MPV_EVENT_FILE_LOADED && m_open) {
            char *path = mpv_get_property_string(handle, "path");
            const bool matches = QString::fromUtf8(path) == m_path;
            mpv_free(path);
            if (!matches)
                continue;
            m_loaded = true;
            double duration = 0;
            if (mpv_get_property(handle, "duration", MPV_FORMAT_DOUBLE, &duration) >= 0)
                setDuration(qRound64(duration * 1000));
            applySeek();
            applyPlayback();
        } else if (event->event_id == MPV_EVENT_END_FILE && m_open) {
            const auto *end = static_cast<mpv_event_end_file *>(event->data);
            if (end->reason == MPV_END_FILE_REASON_ERROR) {
                stop();
                setError(QString::fromUtf8(mpv_error_string(end->error)));
            }
        } else if (event->event_id == MPV_EVENT_PROPERTY_CHANGE && m_loaded) {
            const auto *prop = static_cast<mpv_event_property *>(event->data);
            if (prop->format == MPV_FORMAT_NONE)
                continue;
            const QByteArray name(prop->name);
            if (name == "time-pos")
                setPosition(qRound64(*static_cast<double *>(prop->data) * 1000));
            else if (name == "duration") {
                setDuration(qRound64(*static_cast<double *>(prop->data) * 1000));
                applySeek();
            } else if (name == "eof-reached") {
                m_eof = *static_cast<int *>(prop->data);
                if (m_eof)
                    setPlaying(false);
            } else if (name == "hwdec-current") {
                m_hardwareDecoder = QString::fromUtf8(*static_cast<char **>(prop->data));
                emit hardwareDecoderChanged();
            }
        }
    }
}

void MpvOutput::setPosition(qint64 value) {
    if (value != m_position) {
        m_position = value;
        emit positionChanged();
    }
}

void MpvOutput::setDuration(qint64 value) {
    if (value != m_duration) {
        m_duration = value;
        emit durationChanged();
    }
}

void MpvOutput::setPlaying(bool value) {
    if (value != m_playing) {
        m_playing = value;
        emit playingChanged();
    }
}

void MpvOutput::setError(const QString &value) {
    if (value != m_error) {
        m_error = value;
        emit playbackErrorChanged();
    }
}

#include "mpvoutput.moc"
