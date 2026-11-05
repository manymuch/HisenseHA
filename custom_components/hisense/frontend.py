"""集成自带前端卡片的自动注册。

让集成在启动时自己完成：
1) 通过 HA HTTP 静态路径暴露 www/ 下的卡片 js 与冰箱示意图
2) 写进 Lovelace 资源表（等价于用户在「仪表盘 → 资源」里手填）
YAML 模式资源表不可写时，退回官方 add_extra_js_url。

参考 AlexxIT/WebRTC 与 hacs 官方 plugin 自动注册的实现方式；
URL 带 ``?v=<manifest version>`` 做版本缓存 busting。
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

from .const import (
    CARD_IMAGE_FILENAME,
    CARD_IMAGE_URL_PATH,
    CARD_JS_FILENAME,
    CARD_LEGACY_URL_PREFIXES,
    CARD_URL_PATH,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

# 随集成分发的卡片目录：custom_components/<domain>/www/
CARD_DIR = Path(__file__).parent / "www"
CARD_FILE = CARD_DIR / CARD_JS_FILENAME
CARD_IMAGE_FILE = CARD_DIR / CARD_IMAGE_FILENAME


async def async_setup_card(hass: HomeAssistant) -> None:
    """Lovelace 就绪后注册卡片（由 __init__.async_setup 调用）。

    集成 setup 时 Lovelace 可能尚未加载完，故先检查；
    没就绪则监听 EVENT_COMPONENT_LOADED，并以「HA 启动完成」兜底。
    （旧 API ``helpers.start.async_when_setup`` 已在 HA 2026.x 被移除，
    现改用官方事件 + async_at_started。）
    """
    if _is_lovelace_ready(hass):
        await async_register_card(hass)
        return

    from homeassistant.const import EVENT_COMPONENT_LOADED
    from homeassistant.helpers.start import async_at_started

    done: dict[str, bool] = {"registered": False}
    unsub_loaded: Any = None

    async def _register_once() -> None:
        if done["registered"]:
            return
        done["registered"] = True
        if unsub_loaded is not None:
            unsub_loaded()
        await async_register_card(hass)

    async def _on_component_loaded(event: Any) -> None:
        if event.data.get("component") == "lovelace":
            await _register_once()

    unsub_loaded = hass.bus.async_listen(EVENT_COMPONENT_LOADED, _on_component_loaded)

    async def _on_started(_hass: HomeAssistant) -> None:
        await _register_once()  # 兜底：Lovelace 没加载时 extra_js_url 仍能注册

    async_at_started(hass, _on_started)


def _is_lovelace_ready(hass: HomeAssistant) -> bool:
    return "lovelace" in hass.data or "lovelace" in hass.config.components


async def async_register_card(hass: HomeAssistant) -> bool:
    """注册：静态路径 + Lovelace 资源。返回是否至少成功一种方式。"""
    card_file = _find_card_file(hass)
    if card_file is None:
        _LOGGER.warning("未找到卡片文件 %s，跳过前端资源自动注册", CARD_JS_FILENAME)
        return False

    version = await _async_get_version(hass)
    url = f"{CARD_URL_PATH}?v={version}"  # 版本号变化 → 浏览器丢弃旧缓存

    await _async_register_static_path(hass, CARD_URL_PATH, card_file)
    if CARD_IMAGE_FILE.is_file():
        await _async_register_static_path(hass, CARD_IMAGE_URL_PATH, CARD_IMAGE_FILE)

    if await _async_add_lovelace_resource(hass, url):
        return True
    return _async_add_extra_js_url(hass, url)  # YAML 模式兜底


def _find_card_file(hass: HomeAssistant) -> Path | None:
    """按优先级找卡片 js：首选集成自带 www/（HACS 会一起下载），
    回落到用户手工放的 config/www 旧位置。"""
    candidates = (
        CARD_FILE,
        Path(hass.config.path("www", DOMAIN, CARD_JS_FILENAME)),
        Path(hass.config.path("www", CARD_JS_FILENAME)),
    )
    for path in candidates:
        if path.is_file():
            return path
    return None


async def _async_get_version(hass: HomeAssistant) -> str:
    """取集成版本号，优先 HA loader，失败则直接读 manifest.json。"""
    try:
        from homeassistant.loader import async_get_integration

        integration = await async_get_integration(hass, DOMAIN)
        if integration.version:
            return str(integration.version)
    except Exception:  # noqa: BLE001
        pass
    try:
        manifest = json.loads(
            (Path(__file__).parent / "manifest.json").read_text(encoding="utf-8")
        )
        return str(manifest.get("version") or "0")
    except Exception:  # noqa: BLE001
        return "0"


async def _async_register_static_path(
    hass: HomeAssistant, url_path: str, file_path: Path
) -> bool:
    """HA 2024.7+ 推荐 async_register_static_paths([StaticPathConfig(...)])。"""
    try:
        from homeassistant.components.http import StaticPathConfig

        await hass.http.async_register_static_paths(
            [StaticPathConfig(url_path, str(file_path), True)]
        )
        return True
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("注册静态路径 %s 失败: %s", url_path, err)
        return False


def _is_card_resource(url: str) -> bool:
    path = url.split("?", 1)[0].rstrip("/")
    if path.rsplit("/", 1)[-1] != CARD_JS_FILENAME:
        return False
    return path == CARD_URL_PATH or any(
        path.startswith(p) for p in CARD_LEGACY_URL_PREFIXES
    )


def _async_get_resources(hass: HomeAssistant) -> Any | None:
    """取到『可写』的 Lovelace 资源集合，否则返回 None。

    - HA 2025.2 之前 hass.data["lovelace"] 是 dict（取 ["resources"]），
      之后是 dataclass（取 .resources）。
    - YAML 模式资源来自配置文件，无 .store 即不可写，返回 None。
    """
    lovelace = hass.data.get("lovelace")
    if lovelace is None:
        return None
    resources = getattr(lovelace, "resources", None)
    if resources is None and hasattr(lovelace, "get"):
        resources = lovelace.get("resources")
    if resources is None or getattr(resources, "store", None) is None:
        return None
    return resources


async def _async_add_lovelace_resource(hass: HomeAssistant, url: str) -> bool:
    """写进 Lovelace 资源表（GUI 模式下的资源表）。"""
    resources = _async_get_resources(hass)
    if resources is None:
        return False  # 不可写 → 调用方走 extra_js_url
    try:
        if not resources.loaded:
            await resources.async_load()
        matched = [
            it
            for it in resources.async_items()
            if _is_card_resource(it.get("url", ""))
        ]
        if not matched:
            await resources.async_create_item({"res_type": "module", "url": url})
            return True
        for it in matched[1:]:  # 去重：只留一条
            await resources.async_delete_item(it["id"])
        keep = matched[0]
        if keep.get("url") != url:  # 版本变了 → 更新，触发浏览器重拉
            await resources.async_update_item(
                keep["id"], {"res_type": "module", "url": url}
            )
        return True
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("写入资源表失败: %s", err)
        return False


async def async_remove_card(hass: HomeAssistant) -> bool:
    """卸载集成时从资源表删除本卡片条目（补上避免残留 404）。"""
    resources = _async_get_resources(hass)
    if resources is None:
        return False
    try:
        if not resources.loaded:
            await resources.async_load()
        matched = [
            it
            for it in resources.async_items()
            if _is_card_resource(it.get("url", ""))
        ]
        for it in matched:
            await resources.async_delete_item(it["id"])
        return bool(matched)
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("移除卡片资源失败: %s", err)
        return False


def _async_add_extra_js_url(hass: HomeAssistant, url: str) -> bool:
    """官方公开 API，兜底 YAML 模式等资源表不可写的场景。"""
    try:
        from homeassistant.components.frontend import add_extra_js_url

        add_extra_js_url(hass, url)
        return True
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("注册卡片前端资源失败，需手工添加资源 %s: %s", url, err)
        return False
