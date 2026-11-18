from __future__ import annotations

import asyncio
import datetime
import json
import logging

from homeassistant import config_entries, core
from homeassistant.components import persistent_notification
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_PASSWORD, CONF_USERNAME, DOMAIN
from .coordinator import HisenseDataUpdateCoordinator
from .pyhisenseapi import (
    HiSenseAC,
    HiSenseDryer,
    HiSenseFridge,
    HiSenseTV,
    HiSenseWasher,
    HiSenseOven,
    HiSenseDishwasher,
    HiSenseWaterHeater,
    HiSenseHood,
    HiSenseStove,
    HiSenseDehumidifier,
    HiSenseFreshAir,
    HiSenseWineCabinet,
    WASHER_PROGRAM_REVERSE_MAP,
    WASHER_DRY_REVERSE_MAP,
    OVEN_RUN_STATUS_MAP,
    OVEN_MODE_REVERSE_MAP,
    DISHWASHER_RUN_STATUS_MAP,
    DISHWASHER_PROGRAM_REVERSE_MAP,
    HOOD_SPEED_REVERSE_MAP,
    DEHUMIDIFIER_MODE_REVERSE_MAP,
    FRESH_AIR_MODE_REVERSE_MAP,
)
from .mqtt_client import HisenseMQTTManager

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: core.HomeAssistant, entry: config_entries.ConfigEntry):
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {}
    session = async_get_clientsession(hass)
    clients = []
    coordinators = []
    token_lock = asyncio.Lock()
    mqtt_manager: HisenseMQTTManager | None = None

    def save_tokens(access_token, refresh_token, customer_id):
        """Keep every device and the config entry on the same token pair."""
        for client in clients:
            client.access_token = access_token
            client.refresh_token = refresh_token
            client.customer_id = customer_id
        if mqtt_manager:
            mqtt_manager.access_token = access_token
            mqtt_manager.customer_id = customer_id
        devices = [
            {
                **device,
                "access_token": access_token,
                "refresh_token": refresh_token,
                "customer_id": customer_id,
            }
            for device in entry.data["devices"]
        ]
        hass.config_entries.async_update_entry(entry, data={**entry.data, "devices": devices})

    username = entry.data.get(CONF_USERNAME, "")
    password = entry.data.get(CONF_PASSWORD, "")
    if not username or not password:
        entry.async_start_reauth(hass)

    for device_info in entry.data["devices"]:
        device_id = device_info["device_id"]
        wifi_id = device_info["wifi_id"]
        refresh_token = device_info["refresh_token"]
        access_token = device_info.get("access_token")
        customer_id = device_info.get("customer_id", "")
        partner_id = device_info.get("partner_id", "1001")
        home_id = device_info.get("home_id", "")
        device_type = device_info.get("device_type", "空调")
        device_type_name = device_info.get("device_type_name", "")
        device_name = device_info.get("device_name", "")
        device_code = device_info.get("device_code", "")

        # 组合显示名。device_type_name 在部分机型上会回退成产品型号（与
        # device_name 相同），此时不要重复拼接成 "型号_型号"。
        if device_type_name and device_name:
            if device_type_name == device_name:
                friendly_name = device_name
            else:
                friendly_name = f"{device_type_name}_{device_name}"
        else:
            friendly_name = device_type_name or device_name or device_id
        entity_name = device_code if device_code else device_id

        if device_type == "洗衣机":
            client = HiSenseWasher(
                wifi_id=wifi_id,
                device_id=device_id,
                refresh_token=refresh_token,
                session=session,
                device_name=friendly_name,
                entity_name=entity_name,
                home_id=home_id,
                access_token=access_token,
                customer_id=customer_id,
                partner_id=partner_id,
                username=username,
                password=password,
                on_token_refresh=save_tokens,
                token_lock=token_lock,
            )
        elif device_type == "干衣机":
            client = HiSenseDryer(
                wifi_id=wifi_id,
                device_id=device_id,
                refresh_token=refresh_token,
                session=session,
                device_name=friendly_name,
                entity_name=entity_name,
                home_id=home_id,
                access_token=access_token,
                customer_id=customer_id,
                partner_id=partner_id,
                username=username,
                password=password,
                on_token_refresh=save_tokens,
                token_lock=token_lock,
            )
        elif device_type == "冰箱":
            client = HiSenseFridge(
                wifi_id=wifi_id,
                device_id=device_id,
                refresh_token=refresh_token,
                session=session,
                device_name=friendly_name,
                entity_name=entity_name,
                home_id=home_id,
                access_token=access_token,
                customer_id=customer_id,
                partner_id=partner_id,
                username=username,
                password=password,
                on_token_refresh=save_tokens,
                token_lock=token_lock,
            )
        elif device_type == "电视":
            client = HiSenseTV(
                wifi_id=wifi_id,
                device_id=device_id,
                refresh_token=refresh_token,
                session=session,
                device_name=friendly_name,
                entity_name=entity_name,
                home_id=home_id,
                access_token=access_token,
                customer_id=customer_id,
                partner_id=partner_id,
                username=username,
                password=password,
                on_token_refresh=save_tokens,
                token_lock=token_lock,
            )
        elif device_type == "烤箱":
            client = HiSenseOven(
                wifi_id=wifi_id,
                device_id=device_id,
                refresh_token=refresh_token,
                session=session,
                device_name=friendly_name,
                entity_name=entity_name,
                home_id=home_id,
                access_token=access_token,
                customer_id=customer_id,
                partner_id=partner_id,
                username=username,
                password=password,
                on_token_refresh=save_tokens,
                token_lock=token_lock,
            )
        elif device_type == "洗碗机":
            client = HiSenseDishwasher(
                wifi_id=wifi_id,
                device_id=device_id,
                refresh_token=refresh_token,
                session=session,
                device_name=friendly_name,
                entity_name=entity_name,
                home_id=home_id,
                access_token=access_token,
                customer_id=customer_id,
                partner_id=partner_id,
                username=username,
                password=password,
                on_token_refresh=save_tokens,
                token_lock=token_lock,
            )
        elif device_type == "热水器":
            client = HiSenseWaterHeater(
                wifi_id=wifi_id,
                device_id=device_id,
                refresh_token=refresh_token,
                session=session,
                device_name=friendly_name,
                entity_name=entity_name,
                home_id=home_id,
                access_token=access_token,
                customer_id=customer_id,
                partner_id=partner_id,
                username=username,
                password=password,
                on_token_refresh=save_tokens,
                token_lock=token_lock,
            )
        elif device_type == "油烟机":
            client = HiSenseHood(
                wifi_id=wifi_id,
                device_id=device_id,
                refresh_token=refresh_token,
                session=session,
                device_name=friendly_name,
                entity_name=entity_name,
                home_id=home_id,
                access_token=access_token,
                customer_id=customer_id,
                partner_id=partner_id,
                username=username,
                password=password,
                on_token_refresh=save_tokens,
                token_lock=token_lock,
            )
        elif device_type == "燃气灶":
            client = HiSenseStove(
                wifi_id=wifi_id,
                device_id=device_id,
                refresh_token=refresh_token,
                session=session,
                device_name=friendly_name,
                entity_name=entity_name,
                home_id=home_id,
                access_token=access_token,
                customer_id=customer_id,
                partner_id=partner_id,
                username=username,
                password=password,
                on_token_refresh=save_tokens,
                token_lock=token_lock,
            )
        elif device_type == "除湿机":
            client = HiSenseDehumidifier(
                wifi_id=wifi_id,
                device_id=device_id,
                refresh_token=refresh_token,
                session=session,
                device_name=friendly_name,
                entity_name=entity_name,
                home_id=home_id,
                access_token=access_token,
                customer_id=customer_id,
                partner_id=partner_id,
                username=username,
                password=password,
                on_token_refresh=save_tokens,
                token_lock=token_lock,
            )
        elif device_type == "新风系统":
            client = HiSenseFreshAir(
                wifi_id=wifi_id,
                device_id=device_id,
                refresh_token=refresh_token,
                session=session,
                device_name=friendly_name,
                entity_name=entity_name,
                home_id=home_id,
                access_token=access_token,
                customer_id=customer_id,
                partner_id=partner_id,
                username=username,
                password=password,
                on_token_refresh=save_tokens,
                token_lock=token_lock,
            )
        elif device_type == "酒柜":
            client = HiSenseWineCabinet(
                wifi_id=wifi_id,
                device_id=device_id,
                refresh_token=refresh_token,
                session=session,
                device_name=friendly_name,
                entity_name=entity_name,
                home_id=home_id,
                access_token=access_token,
                customer_id=customer_id,
                partner_id=partner_id,
                username=username,
                password=password,
                on_token_refresh=save_tokens,
                token_lock=token_lock,
            )
        else:
            client = HiSenseAC(
                wifi_id=wifi_id,
                device_id=device_id,
                refresh_token=refresh_token,
                session=session,
                device_name=friendly_name,
                entity_name=entity_name,
                home_id=home_id,
                access_token=access_token,
                customer_id=customer_id,
                partner_id=partner_id,
                username=username,
                password=password,
                on_token_refresh=save_tokens,
                token_lock=token_lock,
            )

        clients.append(client)
        coordinator = HisenseDataUpdateCoordinator(hass, client, device_type, entry)
        client.on_auth_failure = coordinator.async_start_refresh
        coordinators.append((device_id, coordinator))

    for device_id, coordinator in coordinators:
        hass.data[DOMAIN][entry.entry_id][device_id] = coordinator
        coordinator.async_start_refresh()

    # 初始化并启动海信 MQTT 长连接推送管理器
    active_token = clients[0].access_token if clients else None
    active_customer_id = clients[0].customer_id if clients else None
    if active_token and active_customer_id:
        def on_mqtt_device_change(target_device_id, message_data):
            """MQTT 接收到设备状态变更或模拟推送时触发（已调度至主事件循环运行）."""
            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            target_device_id = str(target_device_id) if target_device_id else None
            is_simulated = message_data.get("_simulated", False) if isinstance(message_data, dict) else False
            refresh_cloud = message_data.get("refresh_cloud", False) if isinstance(message_data, dict) else False

            parsed_text = message_data.get("parsed_text") if isinstance(message_data, dict) else None
            if not parsed_text and isinstance(message_data, dict) and isinstance(message_data.get("text"), str):
                try:
                    parsed_text = json.loads(message_data["text"])
                except Exception:
                    parsed_text = None

            raw_states = None
            change_info = None
            action_val = "onDeviceStateUpdate"
            tag_val = message_data.get("businessTag", "JHkDeviceChangeBizMessage") if isinstance(message_data, dict) else ""

            if isinstance(parsed_text, dict):
                raw_states = parsed_text.get("status")
                change_info = parsed_text.get("changeInfo")
                action_val = parsed_text.get("action", action_val)
                if not target_device_id:
                    target_device_id = parsed_text.get("devId") or parsed_text.get("deviceId")

            # 在 Home Assistant 事件总线上广播通用 MQTT 消息事件
            hass.bus.async_fire(
                "hisense_mqtt_message",
                {
                    "device_id": target_device_id,
                    "data": message_data,
                    "parsed": parsed_text,
                    "timestamp": now_str,
                },
            )

            for dev_id, coord in coordinators:
                if (
                    target_device_id is None
                    or str(dev_id) == target_device_id
                    or (target_device_id and (target_device_id in str(dev_id) or str(dev_id) in target_device_id))
                ):
                    # 1. 无论是完整状态 raw_states 还是增量变更 change_info，均更新客户端内存并刷新实体
                    states_to_update = {}
                    if isinstance(raw_states, dict):
                        states_to_update.update(raw_states)
                    if isinstance(change_info, dict):
                        for k, v in change_info.items():
                            states_to_update[k] = v[0] if isinstance(v, list) else v
                    if states_to_update and hasattr(coord.client, "_update_from_states"):
                        coord.client._update_from_states(states_to_update)
                        coord.async_set_updated_data(coord.client.get_status())

                    # 2. 格式化推送简述
                    summary_str = None
                    if isinstance(change_info, dict):
                        changes = []
                        if "powerStatus" in change_info or "power" in change_info:
                            p_val = change_info.get("powerStatus", change_info.get("power"))
                            p_curr = p_val[0] if isinstance(p_val, list) else p_val
                            changes.append("电源:开机" if str(p_curr) == "1" else "电源:关机")
                        # 空调字段
                        if "setTemperature" in change_info:
                            t_val = change_info["setTemperature"]
                            t_curr = t_val[0] if isinstance(t_val, list) else t_val
                            changes.append(f"设定温度:{t_curr}℃")
                        if "realTemperature" in change_info:
                            t_val = change_info["realTemperature"]
                            t_curr = t_val[0] if isinstance(t_val, list) else t_val
                            changes.append(f"室温:{t_curr}℃")
                        if "modes" in change_info:
                            m_val = change_info["modes"]
                            m_curr = m_val[0] if isinstance(m_val, list) else m_val
                            m_name = {0: "送风", 1: "制热", 2: "制冷", 3: "除湿", 4: "自动"}.get(int(m_curr) if str(m_curr).isdigit() else m_curr, f"模式:{m_curr}")
                            changes.append(f"模式:{m_name}")
                        if "windSpeed" in change_info:
                            w_val = change_info["windSpeed"]
                            w_curr = w_val[0] if isinstance(w_val, list) else w_val
                            w_name = {1: "微风", 2: "低风", 3: "中风", 4: "高风"}.get(int(w_curr) if str(w_curr).isdigit() else w_curr, f"风速:{w_curr}")
                            changes.append(f"风速:{w_name}")
                        # 冰箱字段
                        if "refrigeratorSetTemperature" in change_info:
                            t_val = change_info["refrigeratorSetTemperature"]
                            t_curr = t_val[0] if isinstance(t_val, list) else t_val
                            changes.append(f"冷藏:{t_curr}℃")
                        if "freezeSetTemperature" in change_info:
                            t_val = change_info["freezeSetTemperature"]
                            t_curr = t_val[0] if isinstance(t_val, list) else t_val
                            changes.append(f"冷冻:{t_curr}℃")
                        if "dBDDegerming" in change_info:
                            d_val = change_info["dBDDegerming"]
                            d_curr = d_val[0] if isinstance(d_val, list) else d_val
                            changes.append("除菌净味:开" if str(d_curr) == "1" else "除菌净味:关")
                        # 电视字段
                        if "volume" in change_info:
                            v_val = change_info["volume"]
                            v_curr = v_val[0] if isinstance(v_val, list) else v_val
                            changes.append(f"音量:{v_curr}")
                        if "mute" in change_info:
                            m_val = change_info["mute"]
                            m_curr = m_val[0] if isinstance(m_val, list) else m_val
                            changes.append("静音:开" if str(m_curr) == "1" else "静音:关")
                        # 洗衣机 / 干衣机字段
                        if "runStatus" in change_info:
                            r_val = change_info["runStatus"]
                            r_curr = r_val[0] if isinstance(r_val, list) else r_val
                            r_int = int(r_curr) if str(r_curr).isdigit() else None
                            phase_str = {
                                0: "待机",
                                1: "预约等待",
                                2: "主洗",
                                3: "漂洗",
                                4: "脱水",
                                5: "烘干",
                                7: "完成",
                                10: "抖散",
                                11: "防皱",
                            }.get(r_int, f"阶段:{r_curr}")
                            changes.append(f"状态:{phase_str}")
                        if "workMode" in change_info:
                            w_val = change_info["workMode"]
                            w_curr = w_val[0] if isinstance(w_val, list) else w_val
                            w_idx = int(w_curr) if str(w_curr).isdigit() else w_curr
                            w_name = WASHER_PROGRAM_REVERSE_MAP.get(w_idx) or WASHER_PROGRAM_REVERSE_MAP.get(str(w_curr)) or f"程序{w_curr}"
                            changes.append(f"程序:{w_name}")
                        if "dehydrationSpeed" in change_info or "dehydrationDrySwitch" in change_info:
                            s_raw = change_info.get("dehydrationSpeed", change_info.get("dehydrationDrySwitch"))
                            s_curr = s_raw[0] if isinstance(s_raw, list) else s_raw
                            changes.append("不脱水" if str(s_curr) == "0" else f"转速:{s_curr}转")
                        if "washTemperature" in change_info:
                            t_val = change_info["washTemperature"]
                            t_curr = t_val[0] if isinstance(t_val, list) else t_val
                            changes.append(f"水温:{t_curr}℃")
                        if "washTime" in change_info:
                            wt_val = change_info["washTime"]
                            wt_curr = wt_val[0] if isinstance(wt_val, list) else wt_val
                            changes.append(f"洗涤:{wt_curr}分")
                        if "rinsingFrequency" in change_info:
                            rf_val = change_info["rinsingFrequency"]
                            rf_curr = rf_val[0] if isinstance(rf_val, list) else rf_val
                            changes.append(f"漂洗:{rf_curr}次")
                        if "dryingMethod" in change_info:
                            dm_val = change_info["dryingMethod"]
                            dm_curr = dm_val[0] if isinstance(dm_val, list) else dm_val
                            dm_name = WASHER_DRY_REVERSE_MAP.get(str(dm_curr), f"烘干:{dm_curr}")
                            changes.append(f"烘干:{dm_name}")
                        if "dryingModes" in change_info:
                            dms_val = change_info["dryingModes"]
                            dms_curr = dms_val[0] if isinstance(dms_val, list) else dms_val
                            changes.append("低温烘:开" if str(dms_curr) == "1" else "低温烘:关")
                        if "childLock" in change_info:
                            c_val = change_info["childLock"]
                            c_curr = c_val[0] if isinstance(c_val, list) else c_val
                            changes.append("童锁:开" if str(c_curr) == "1" else "童锁:关")
                        if "remainRunTime" in change_info:
                            t_val = change_info["remainRunTime"]
                            t_curr = t_val[0] if isinstance(t_val, list) else t_val
                            changes.append(f"剩余{t_curr}分")
                        # 烤箱 / 洗碗机 / 热水器 / 油烟机 / 除湿机 / 燃气灶字段
                        if "cookTime" in change_info:
                            ct_val = change_info["cookTime"]
                            ct_curr = ct_val[0] if isinstance(ct_val, list) else ct_val
                            changes.append(f"烹饪时长:{ct_curr}分")
                        if "probeTemperature" in change_info:
                            pt_val = change_info["probeTemperature"]
                            pt_curr = pt_val[0] if isinstance(pt_val, list) else pt_val
                            changes.append(f"探针温度:{pt_curr}℃")
                        if "saltLackStatus" in change_info:
                            sl = change_info["saltLackStatus"]
                            sl_curr = sl[0] if isinstance(sl, list) else sl
                            changes.append("缺软水盐" if str(sl_curr) == "1" else "软水盐正常")
                        if "rinseAidLackStatus" in change_info:
                            ra = change_info["rinseAidLackStatus"]
                            ra_curr = ra[0] if isinstance(ra, list) else ra
                            changes.append("缺光亮剂" if str(ra_curr) == "1" else "光亮剂正常")
                        if "realWaterTemperature" in change_info or "setWaterTemperature" in change_info:
                            wt = change_info.get("realWaterTemperature", change_info.get("setWaterTemperature"))
                            wt_curr = wt[0] if isinstance(wt, list) else wt
                            changes.append(f"水温:{wt_curr}℃")
                        if "heatingStatus" in change_info:
                            hs = change_info["heatingStatus"]
                            hs_curr = hs[0] if isinstance(hs, list) else hs
                            changes.append("加热中" if str(hs_curr) == "1" else "保温中")
                        if "lightSwitch" in change_info or "lightSwitchControl" in change_info:
                            ls = change_info.get("lightSwitch", change_info.get("lightSwitchControl"))
                            ls_curr = ls[0] if isinstance(ls, list) else ls
                            changes.append("照明:开" if str(ls_curr) == "1" else "照明:关")
                        if "targetHumidity" in change_info:
                            th = change_info["targetHumidity"]
                            th_curr = th[0] if isinstance(th, list) else th
                            changes.append(f"目标湿度:{th_curr}%")
                        if "waterFullStatus" in change_info:
                            wf = change_info["waterFullStatus"]
                            wf_curr = wf[0] if isinstance(wf, list) else wf
                            changes.append("水箱已满" if str(wf_curr) == "1" else "水箱正常")
                        if "firePower.left" in change_info or "leftFirePower" in change_info:
                            fp = change_info.get("firePower.left", change_info.get("leftFirePower"))
                            fp_curr = fp[0] if isinstance(fp, list) else fp
                            changes.append(f"左灶火力:{fp_curr}")
                        if "firePower.right" in change_info or "rightFirePower" in change_info:
                            fp = change_info.get("firePower.right", change_info.get("rightFirePower"))
                            fp_curr = fp[0] if isinstance(fp, list) else fp
                            changes.append(f"右灶火力:{fp_curr}")
                        if changes:
                            summary_str = " | ".join(changes)

                    # 如果没有具体的变更字段列表，但携带了完整状态字典，生成状态快照
                    if not summary_str and isinstance(raw_states, dict):
                        snapshot = []
                        p_val = raw_states.get("powerStatus")
                        if str(p_val) == "0":
                            snapshot.append("关机")
                        else:
                            snapshot.append("开机")
                            r_val = raw_states.get("runStatus")
                            r_int = int(r_val) if str(r_val).isdigit() else None
                            phase_str = {
                                0: "待机",
                                1: "预约等待",
                                2: "主洗",
                                3: "漂洗",
                                4: "脱水",
                                5: "烘干",
                                7: "完成",
                                10: "抖散",
                                11: "防皱",
                            }.get(r_int, f"阶段:{r_val}")
                            snapshot.append(f"状态:{phase_str}")
                            w_val = raw_states.get("workMode")
                            if w_val:
                                w_idx = int(w_val) if str(w_val).isdigit() else w_val
                                snapshot.append(WASHER_PROGRAM_REVERSE_MAP.get(w_idx) or WASHER_PROGRAM_REVERSE_MAP.get(str(w_val)) or f"程序{w_val}")
                            sp_val = raw_states.get("dehydrationSpeed") or raw_states.get("dehydrationDrySwitch")
                            if sp_val is not None:
                                snapshot.append("不脱水" if str(sp_val) == "0" else f"{sp_val}转")
                            temp_val = raw_states.get("washTemperature")
                            if temp_val is not None:
                                snapshot.append(f"{temp_val}℃")
                            wt_val = raw_states.get("washTime")
                            if wt_val is not None:
                                snapshot.append(f"洗涤{wt_val}分")
                            dm_val = raw_states.get("dryingMethod")
                            if dm_val and str(dm_val) != "0":
                                snapshot.append(f"烘干:{WASHER_DRY_REVERSE_MAP.get(str(dm_val), dm_val)}")
                            if str(raw_states.get("dryingModes")) == "1":
                                snapshot.append("低温烘")
                            rem_val = raw_states.get("remainRunTime")
                            if rem_val:
                                snapshot.append(f"剩余{rem_val}分")
                        if snapshot:
                            summary_str = " | ".join(snapshot)

                    msg_content = None
                    if isinstance(parsed_text, dict):
                        msg_content = parsed_text.get("msgContent") or parsed_text.get("msgTitle")

                    status_val = message_data.get("status") if isinstance(message_data, dict) else None
                    if not summary_str:
                        if msg_content:
                            summary_str = msg_content
                        elif status_val in ("complete", "7"):
                            summary_str = "洗衣完成 (complete)"
                        elif status_val in ("running", "1"):
                            summary_str = "开始运行 (running)"
                        elif status_val in ("standby", "0"):
                            summary_str = "待机中 (standby)"
                        elif status_val == "off":
                            summary_str = "设备关机 (off)"
                        else:
                            summary_str = f"状态变更: {action_val}"

                    # 记录到 Coordinator 供 last_push_message 实体展示与历史回溯
                    push_record = {
                        "timestamp": now_str,
                        "status": status_val,
                        "action": action_val,
                        "businessTag": tag_val,
                        "deviceId": str(dev_id),
                        "summary": summary_str,
                        "raw": message_data,
                        "changeInfo": change_info,
                    }
                    coord.last_push = push_record
                    if not hasattr(coord, "push_history"):
                        coord.push_history = []
                    coord.push_history.append({
                        "time": now_str,
                        "summary": summary_str,
                        "status": status_val,
                        "action": action_val,
                    })
                    if len(coord.push_history) > 30:
                        coord.push_history.pop(0)

                    # 3. 洗衣机 / 干衣机 / 洗碗机 / 烤箱完成检测与专属通知
                    dev_name = getattr(coord.client, "device_name", None) or f"海信{coord.device_type}"
                    is_complete = False
                    if status_val in ("complete", "7", "4"):
                        is_complete = True
                    elif isinstance(change_info, dict) and "runStatus" in change_info:
                        r_val = change_info["runStatus"]
                        r_curr = r_val[0] if isinstance(r_val, list) else r_val
                        if str(r_curr) in ("7", "4"):
                            is_complete = True
                    elif msg_content and any(w in msg_content for w in ("洗衣完毕", "洗涤完成", "烘干完成", "已完成洗衣", "已完成烘干", "洗碗完成", "烹饪完成", "烘烤完成")):
                        is_complete = True
                    elif str(tag_val) == "8001008":
                        is_complete = True

                    if is_complete and coord.device_type in ("洗衣机", "干衣机", "洗碗机", "烤箱"):
                        if hasattr(coord.client, "status") and isinstance(coord.client.status, dict):
                            coord.client.status.update({
                                "run_status": 7 if coord.device_type != "烤箱" else 4,
                                "machine_state": "complete",
                                "cycle_phase": "complete",
                                "is_running": False,
                                "remain_time": 0,
                                "remaining_minutes": 0,
                                "start_pause_status": False,
                            })
                            coord.async_set_updated_data(coord.client.get_status())

                    if is_complete and coord.device_type in ("洗衣机", "干衣机", "洗碗机", "烤箱"):
                        action_name = {
                            "洗衣机": "洗衣",
                            "干衣机": "烘干",
                            "洗碗机": "洗碗",
                            "烤箱": "烹饪",
                        }.get(coord.device_type, "运行")
                        event_type = {
                            "洗衣机": "washer",
                            "干衣机": "dryer",
                            "洗碗机": "dishwasher",
                            "烤箱": "oven",
                        }.get(coord.device_type, "device")
                        content_desc = msg_content or f"【{dev_name}】已完成{action_name}！"
                        hass.bus.async_fire(
                            f"hisense_{event_type}_complete",
                            {
                                "device_id": str(dev_id),
                                "device_name": dev_name,
                                "status": "complete",
                                "message": content_desc,
                                "timestamp": now_str,
                            },
                        )
                        persistent_notification.async_create(
                            hass,
                            f"收到{dev_name}推送：{content_desc}\n推送时间：{now_str}",
                            title=f"海信智慧家 - {action_name}完成提醒",
                            notification_id=f"hisense_{event_type}_complete_{dev_id}",
                        )

                    # 立即刷新所有绑定该 coordinator 的实体状态
                    coord.async_update_listeners()

                    # 如果没有直接携带完整状态字典，或者明确要求云端同步，才发起异步云端拉取
                    if raw_states is None and (not is_simulated or refresh_cloud):
                        coord.async_start_refresh()

        extra_topics = []
        for dev_id, _ in coordinators:
            extra_topics.append(f"$iot/{dev_id}/#")
            if ":" in str(dev_id):
                for part in str(dev_id).split(":"):
                    if part:
                        extra_topics.append(f"$iot/{part}/#")

        mqtt_manager = HisenseMQTTManager(
            session=session,
            access_token=active_token,
            customer_id=active_customer_id,
            on_message_callback=on_mqtt_device_change,
            loop=hass.loop,
            extra_topics=extra_topics,
        )
        hass.data[DOMAIN][f"{entry.entry_id}_mqtt"] = mqtt_manager

        # 注册模拟 MQTT 消息服务供测试自动化联动
        if not hass.services.has_service(DOMAIN, "simulate_mqtt_message"):
            async def handle_simulate_mqtt_message(call):
                target_dev = call.data.get("device_id")
                status = call.data.get("status")
                raw_payload = call.data.get("raw_payload")
                refresh_cloud = call.data.get("refresh_cloud", False)
                payload = dict(raw_payload) if isinstance(raw_payload, dict) else {"status": status or "complete"}
                payload["_simulated"] = True
                payload["refresh_cloud"] = refresh_cloud
                for key, val in hass.data[DOMAIN].items():
                    if key.endswith("_mqtt") and isinstance(val, HisenseMQTTManager):
                        val.simulate_message(target_dev, payload)

            hass.services.async_register(DOMAIN, "simulate_mqtt_message", handle_simulate_mqtt_message)

        # 异步启动 MQTT 长连接
        if hasattr(entry, "async_create_background_task"):
            entry.async_create_background_task(hass, mqtt_manager.start(), "Hisense MQTT Client")
        else:
            hass.async_create_task(mqtt_manager.start())

    platforms = [
        "climate",
        "switch",
        "button",
        "number",
        "sensor",
        "binary_sensor",
        "select",
        "media_player",
    ]
    await hass.config_entries.async_forward_entry_setups(entry, platforms)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_reload_entry(hass: core.HomeAssistant, entry: config_entries.ConfigEntry) -> None:
    """Reload config entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: core.HomeAssistant, entry: config_entries.ConfigEntry):
    platforms = [
        "climate",
        "switch",
        "button",
        "number",
        "sensor",
        "binary_sensor",
        "select",
        "media_player",
    ]
    unload_ok = await hass.config_entries.async_unload_platforms(entry, platforms)
    if unload_ok:
        mqtt_manager = hass.data[DOMAIN].pop(f"{entry.entry_id}_mqtt", None)
        if mqtt_manager and isinstance(mqtt_manager, HisenseMQTTManager):
            await mqtt_manager.stop()

        for coordinator in hass.data[DOMAIN].get(entry.entry_id, {}).values():
            await coordinator.async_cancel_refresh()
        hass.data[DOMAIN].pop(entry.entry_id, None)

        # 若无存活 entry，注销测试服务
        active_entries = [k for k in hass.data[DOMAIN] if not k.endswith("_mqtt")]
        if not active_entries and hass.services.has_service(DOMAIN, "simulate_mqtt_message"):
            hass.services.async_remove(DOMAIN, "simulate_mqtt_message")

    return unload_ok
