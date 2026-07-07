"""
Модуль плавных анимаций для SecureSysAdmin.
Все анимации можно включать/отключать глобально.
"""
from __future__ import annotations

from PyQt6.QtCore import (
    QPropertyAnimation,
    QEasingCurve,
    QParallelAnimationGroup,
    QSequentialAnimationGroup,
    QPoint,
    QSize,
    pyqtProperty,
    QObject,
)
from PyQt6.QtWidgets import QWidget, QGraphicsOpacityEffect


# ── Глобальный флаг ────────────────────────────────────────────────────────
_animations_enabled: bool = True


def set_animations_enabled(enabled: bool) -> None:
    """Глобально включает/выключает анимации."""
    global _animations_enabled
    _animations_enabled = enabled


def animations_enabled() -> bool:
    """Возвращает True, если анимации включены."""
    return _animations_enabled


# ── Вспомогательные фабрики ────────────────────────────────────────────────

def _quick_anim(target: QObject, prop: bytes, duration: int = 200,
                start=None, end=None,
                curve: QEasingCurve.Type = QEasingCurve.Type.OutCubic):
    """Создаёт одно QPropertyAnimation с плавной кривой."""
    anim = QPropertyAnimation(target, prop)
    anim.setDuration(duration if _animations_enabled else 0)
    anim.setEasingCurve(curve)
    if start is not None:
        anim.setStartValue(start)
    if end is not None:
        anim.setEndValue(end)
    return anim


# ── Публичные функции ─────────────────────────────────────────────────────

def fade_in(widget: QWidget, duration: int = 250,
            curve: QEasingCurve.Type = QEasingCurve.Type.OutCubic) -> QPropertyAnimation | None:
    """Плавное появление (opacity 0 → 1)."""
    if not _animations_enabled:
        widget.setVisible(True)
        return None
    effect = widget.graphicsEffect()
    if not isinstance(effect, QGraphicsOpacityEffect):
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)
    widget.setVisible(True)
    effect.setOpacity(0.0)
    anim = QPropertyAnimation(effect, b"opacity")
    anim.setDuration(duration)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(curve)
    anim.start()
    return anim


def fade_out(widget: QWidget, duration: int = 200,
             curve: QEasingCurve.Type = QEasingCurve.Type.InCubic,
             hide_after: bool = True) -> QPropertyAnimation | None:
    """Плавное исчезновение (opacity 1 → 0). По завершении скрывает виджет."""
    if not _animations_enabled:
        if hide_after:
            widget.setVisible(False)
        return None
    effect = widget.graphicsEffect()
    if not isinstance(effect, QGraphicsOpacityEffect):
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)
    effect.setOpacity(1.0)
    anim = QPropertyAnimation(effect, b"opacity")
    anim.setDuration(duration)
    anim.setStartValue(1.0)
    anim.setEndValue(0.0)
    anim.setEasingCurve(curve)
    if hide_after:
        anim.finished.connect(widget.hide)
    anim.start()
    return anim


def slide_in_top(widget: QWidget, duration: int = 300) -> QPropertyAnimation | None:
    """Выезд виджета сверху вниз до своей позиции."""
    if not _animations_enabled:
        widget.setVisible(True)
        return None
    target_y = widget.y()
    start_y = target_y - 30
    widget.move(widget.x(), start_y)
    widget.setVisible(True)
    anim = _quick_anim(widget, b"pos", duration,
                       start=QPoint(widget.x(), start_y),
                       end=QPoint(widget.x(), target_y),
                       curve=QEasingCurve.Type.OutBack)
    anim.start()
    return anim


def slide_in_bottom(widget: QWidget, duration: int = 300) -> QPropertyAnimation | None:
    """Выезд виджета снизу вверх."""
    if not _animations_enabled:
        widget.setVisible(True)
        return None
    target_y = widget.y()
    start_y = target_y + 30
    widget.move(widget.x(), start_y)
    widget.setVisible(True)
    anim = _quick_anim(widget, b"pos", duration,
                       start=QPoint(widget.x(), start_y),
                       end=QPoint(widget.x(), target_y),
                       curve=QEasingCurve.Type.OutBack)
    anim.start()
    return anim


def tab_switch_animation(stacked_widget, index: int, duration: int = 200):
    """
    Анимация переключения вкладки в QStackedWidget.
    Лёгкое затухание текущей и появление новой.
    """
    if not _animations_enabled:
        stacked_widget.setCurrentIndex(index)
        return

    current_widget = stacked_widget.currentWidget()
    target_widget = stacked_widget.widget(index)

    if current_widget is target_widget:
        return

    # fade-out current
    if current_widget:
        fo = fade_out(current_widget, duration=150, hide_after=False)
        if fo:
            fo.finished.connect(lambda: _switch_and_fade_in(stacked_widget, target_widget, duration))
            return

    _switch_and_fade_in(stacked_widget, target_widget, duration)


def _switch_and_fade_in(stacked, target, duration):
    stacked.setCurrentWidget(target)
    target.setVisible(True)
    fade_in(target, duration=duration)


def pulse(widget: QWidget, duration: int = 400) -> QSequentialAnimationGroup | None:
    """Пульсация: scale 1.0 → 1.03 → 1.0."""
    if not _animations_enabled:
        return None

    # Сохраняем исходный размер
    base_size = widget.size()

    # Для простоты используем opacity-пульсацию вместо геометрической
    # (геометрия может сломать лэйауты)
    effect = widget.graphicsEffect()
    if not isinstance(effect, QGraphicsOpacityEffect):
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)
    effect.setOpacity(1.0)

    anim_out = QPropertyAnimation(effect, b"opacity")
    anim_out.setDuration(duration // 2)
    anim_out.setStartValue(1.0)
    anim_out.setEndValue(0.7)
    anim_out.setEasingCurve(QEasingCurve.Type.OutCubic)

    anim_in = QPropertyAnimation(effect, b"opacity")
    anim_in.setDuration(duration // 2)
    anim_in.setStartValue(0.7)
    anim_in.setEndValue(1.0)
    anim_in.setEasingCurve(QEasingCurve.Type.InCubic)

    group = QSequentialAnimationGroup()
    group.addAnimation(anim_out)
    group.addAnimation(anim_in)
    group.start()
    return group


__all__ = [
    "set_animations_enabled",
    "animations_enabled",
    "fade_in",
    "fade_out",
    "slide_in_top",
    "slide_in_bottom",
    "tab_switch_animation",
    "pulse",
]