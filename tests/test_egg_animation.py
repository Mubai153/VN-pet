from PIL import Image

from codex_desktop_pet import ANIMATION_SCALE, EGG_ANIMATION_ASSET, EGG_ANIMATION_FRAMES, split_egg_strip, update_click_sequence


def test_three_click_sequence_triggers_only_on_third_click():
    count = 0
    last = 0.0
    for now in (1.0, 1.4, 1.8):
        count, last, triggered = update_click_sequence(count, last, now)
    assert triggered and count == 3


def test_click_sequence_resets_after_timeout():
    count, last, triggered = update_click_sequence(2, 1.0, 2.3)
    assert (count, last, triggered) == (1, 2.3, False)


def test_egg_frames_are_resized_to_the_canvas_frame():
    strip = Image.open(EGG_ANIMATION_ASSET)
    base_size = (strip.width // EGG_ANIMATION_FRAMES // 2, strip.height // 2)
    frames = split_egg_strip(strip, tuple(round(value * ANIMATION_SCALE) for value in base_size))
    assert len(frames) == EGG_ANIMATION_FRAMES
    assert {frame.size for frame in frames} == {(83, 152)}
