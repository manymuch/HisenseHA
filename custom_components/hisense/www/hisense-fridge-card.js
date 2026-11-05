/**
 * hisense-fridge-card — 海信冰箱可视化卡片（HisenseHA 集成自带）
 *
 * 特性：
 *  - 冰箱示意图分区热点：冷藏 / 变温 / 冷冻 三区，显示实际温度与设定温度
 *  - 点击分区或信息卡 → 弹出对应实体详情（more-info）
 *  - 工作模式（智能/速冷）、变温空间档位、除菌+净味 开关可直接操作
 *  - 门未关告警红色角标；离线置灰提示
 *  - 支持通过 name_prefix 指定实体前缀，entities 可逐项覆盖
 *
 * 零第三方依赖（无 lit），仅原生 Custom Element + Shadow DOM。
 */

const CARD_NAME = "hisense-fridge-card";

/** 默认实体 ID 模板（name_prefix → 完整 entity_id） */
function defaultEntities(prefix) {
  const p = prefix || "hai_xin_bing_xiang";
  return {
    fridgeActual: `sensor.${p}_temperature_refrigerator_actual`,
    fridgeSet: `number.${p}_set_temperature_refrigerator`,
    freezerActual: `sensor.${p}_temperature_freezer_actual`,
    freezerSet: `number.${p}_set_temperature_freezer`,
    variation: `select.${p}_setting_variation_drawer`,
    workMode: `select.${p}_setting_work_mode`,
    degerming: `switch.${p}_degerming_odor_removal`,
    power: `binary_sensor.${p}_power`,
    online: `binary_sensor.${p}_connectivity`,
    compressor: `sensor.${p}_compressor_frequency`,
    updated: `sensor.${p}_last_data_update`,
    alarmFridgeDoor: `binary_sensor.${p}_alarm_refrigerator_door_open`,
    alarmFreezerDoor: `binary_sensor.${p}_alarm_freezer_door_open`,
    alarmVariationDoor: `binary_sensor.${p}_alarm_variation_drawer_door_open`,
  };
}

const VARIATION_OPTIONS = ["原鲜", "0℃养鲜", "母婴"];
const WORK_MODE_CHIPS = ["智能", "速冷"];

function esc(s) {
  return String(s == null ? "" : s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function fmtTemp(stateObj) {
  if (!stateObj || stateObj.state === "unavailable" || stateObj.state === "unknown") return "--";
  const n = parseFloat(stateObj.state);
  if (isNaN(n)) return esc(stateObj.state);
  return (Object.is(n, -0) ? 0 : n).toString();
}

class HisenseFridgeCard extends HTMLElement {
  static get tagName() {
    return CARD_NAME;
  }

  // 仪表盘卡片选择器里显示
  static getStubConfig() {
    return { name_prefix: "hai_xin_bing_xiang" };
  }

  static getConfigElement() {
    if (!customElements.get(`${CARD_NAME}-editor`)) {
      customElements.define(`${CARD_NAME}-editor`, HisenseFridgeCardEditor);
    }
    return document.createElement(`${CARD_NAME}-editor`);
  }

  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = null;
    this._config = {};
    this._pendingRender = false;
    this.shadowRoot.addEventListener("click", (ev) => this._onClick(ev));
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._pendingRender) {
      this._pendingRender = true;
      requestAnimationFrame(() => {
        this._pendingRender = false;
        this._render();
      });
    }
  }

  get hass() {
    return this._hass;
  }

  setConfig(config) {
    if (!config || typeof config !== "object") {
      throw new Error("配置错误");
    }
    const overrides = config.entities || {};
    this._config = {
      name: config.name || "",
      image: config.image || "/hisense/hisense-fridge.png",
      name_prefix: config.name_prefix || "hai_xin_bing_xiang",
      entities: { ...defaultEntities(config.name_prefix), ...overrides },
    };
    this._render();
  }

  getCardSize() {
    return 7;
  }

  /* ------------------------------------------------------------------ */
  /* 数据读取                                                            */
  /* ------------------------------------------------------------------ */

  _state(key) {
    const eid = this._config.entities[key];
    if (!eid) return null;
    return this._hass ? this._hass.states[eid] : null;
  }

  _deviceId() {
    const st = this._state("fridgeActual") || this._state("workMode");
    if (st && st.attributes && st.attributes.device_id) return st.attributes.device_id;
    return null;
  }

  _deviceName() {
    if (this._config.name) return this._config.name;
    const st = this._state("fridgeActual") || this._state("workMode");
    if (st && st.attributes && st.attributes.friendly_name) {
      const fn = String(st.attributes.friendly_name);
      const token = fn.split(/\s+/)[0];
      if (token) return token;
    }
    return "海信冰箱";
  }

  _isOn(key) {
    const st = this._state(key);
    return !!st && st.state === "on";
  }

  _isOnline() {
    const st = this._state("online");
    return !st || st.state !== "off"; // 实体缺失时不误报离线
  }

  /* ------------------------------------------------------------------ */
  /* 渲染                                                                */
  /* ------------------------------------------------------------------ */

  _render() {
    if (!this.shadowRoot || !this._config) return;
    const h = this._hass;
    const online = this._isOnline();
    const powered = this._isOn("power");

    const fridgeActual = fmtTemp(this._state("fridgeActual"));
    const fridgeSet = fmtTemp(this._state("fridgeSet"));
    const freezerActual = fmtTemp(this._state("freezerActual"));
    const freezerSet = fmtTemp(this._state("freezerSet"));
    const variationSt = this._state("variation");
    const variation = variationSt && !["unavailable", "unknown"].includes(variationSt.state)
      ? esc(variationSt.state) : "--";
    const workModeSt = this._state("workMode");
    const workMode = workModeSt && !["unavailable", "unknown"].includes(workModeSt.state)
      ? esc(workModeSt.state) : "--";
    const degermingOn = this._isOn("degerming");
    const compressorSt = this._state("compressor");
    const compressor = compressorSt && !["unavailable", "unknown", "--"].includes(compressorSt.state)
      ? esc(compressorSt.state) : "--";

    const alarmFridge = this._isOn("alarmFridgeDoor");
    const alarmFreezer = this._isOn("alarmFreezerDoor");
    const alarmVariation = this._isOn("alarmVariationDoor");

    const updatedSt = this._state("updated");
    const updatedText = updatedSt && updatedSt.last_changed
      ? this._relativeTime(new Date(updatedSt.last_changed))
      : "";

    const image = esc(this._config.image);
    const name = esc(this._deviceName());

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
        }
        ha-card {
          display: block;
          padding: 14px 16px 12px;
          background: var(--card-background-color, var(--ha-card-background, #fff));
          color: var(--primary-text-color, #212121);
          border-radius: var(--ha-card-border-radius, 12px);
          box-shadow: var(--ha-card-box-shadow, none);
          border: 1px solid var(--ha-card-border-color, rgba(0,0,0,0.08));
          overflow: hidden;
        }
        .offline .figure { opacity: 0.35; filter: grayscale(0.8); }
        .header {
          display: flex; align-items: center; gap: 8px;
          margin-bottom: 8px;
        }
        .header ha-icon { color: var(--primary-color, #03a9f4); }
        .title { font-size: 16px; font-weight: 600; flex: 1; }
        .badge {
          font-size: 11px; padding: 2px 8px; border-radius: 10px;
          background: var(--success-color, #43a047); color: #fff;
        }
        .badge.off { background: var(--error-color, #e53935); }
        .badge.power-off { background: var(--secondary-text-color, #727272); }

        .figure {
          position: relative; width: 100%;
          user-select: none; -webkit-user-select: none;
        }
        .figure img {
          display: block; width: 100%; border-radius: 8px;
          pointer-events: none;
        }
        /* 分区热点（覆盖在冰箱内部对应区域） */
        .hotspot {
          position: absolute; cursor: pointer; border: none;
          background: transparent; padding: 0;
        }
        .hotspot:focus-visible { outline: 2px solid var(--primary-color); }

        /* 引线端信息卡 */
        .chip {
          position: absolute; cursor: pointer;
          background: var(--card-background-color, #fff);
          border: 1px solid rgba(0,0,0,0.12);
          border-radius: 10px;
          padding: 4px 10px 5px;
          text-align: left; line-height: 1.25;
          box-shadow: 0 1px 4px rgba(0,0,0,0.15);
          font: inherit; color: inherit;
          min-width: 84px;
          transition: transform .12s ease;
        }
        .chip:active { transform: scale(0.97); }
        .chip .zone { font-size: 11px; opacity: 0.72; display: flex; align-items: center; gap: 4px; }
        .chip .val { font-size: 20px; font-weight: 700; }
        .chip .val small { font-size: 12px; font-weight: 400; opacity: 0.6; }
        .chip .set { font-size: 11px; opacity: 0.66; display: flex; align-items: center; gap: 2px; }
        .chip .edit {
          border: none; background: none; color: var(--primary-color, #03a9f4);
          cursor: pointer; padding: 0 2px; font-size: 12px;
        }
        .alarm-dot {
          width: 8px; height: 8px; border-radius: 50%;
          background: var(--error-color, #e53935);
          display: inline-block;
          animation: blink 1.2s ease-in-out infinite;
        }
        @keyframes blink { 50% { opacity: 0.25; } }

        .controls { margin-top: 10px; display: flex; flex-direction: column; gap: 8px; }
        .ctrl-row { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
        .ctrl-label {
          font-size: 12px; opacity: 0.66; min-width: 62px;
          display: flex; align-items: center; gap: 4px;
        }
        .pill {
          border: 1px solid rgba(0,0,0,0.14);
          background: transparent; color: inherit;
          font-size: 13px; padding: 4px 12px; border-radius: 14px;
          cursor: pointer; font: inherit;
        }
        .pill.active {
          background: var(--primary-color, #03a9f4);
          border-color: var(--primary-color, #03a9f4);
          color: var(--text-primary-color, #fff);
        }
        .pill:disabled { opacity: 0.4; cursor: default; }

        .pill.muted {
          background: rgba(0,0,0,0.06);
          border-color: transparent;
          opacity: 0.8;
        }

        .switch-row { display: flex; align-items: center; justify-content: space-between; }
        .toggle {
          position: relative; width: 40px; height: 22px; border-radius: 11px;
          border: none; cursor: pointer; padding: 0;
          background: rgba(0,0,0,0.25);
          transition: background .15s ease;
        }
        .toggle.on { background: var(--primary-color, #03a9f4); }
        .toggle .knob {
          position: absolute; top: 2px; left: 2px;
          width: 18px; height: 18px; border-radius: 50%;
          background: #fff; box-shadow: 0 1px 3px rgba(0,0,0,0.3);
          transition: left .15s ease;
        }
        .toggle.on .knob { left: 20px; }

        .footer {
          margin-top: 10px; padding-top: 8px;
          border-top: 1px solid rgba(0,0,0,0.08);
          font-size: 11px; opacity: 0.55;
          display: flex; justify-content: space-between; gap: 8px;
        }
      </style>

      <ha-card class="${online ? "" : "offline"}">
        <div class="header">
          <ha-icon icon="mdi:fridge"></ha-icon>
          <span class="title">${name}</span>
          ${powered ? "" : `<span class="badge power-off">断电</span>`}
          ${online ? `<span class="badge">在线</span>` : `<span class="badge off">离线</span>`}
        </div>

        <div class="figure">
          <img src="${image}" alt="冰箱示意图" draggable="false" />
          <!-- 分区热点：直接点冰箱内部区域也弹详情 -->
          <button class="hotspot" data-info="fridgeActual" style="left:38%;top:8%;width:30%;height:33%" aria-label="冷藏室"></button>
          <button class="hotspot" data-info="variation"   style="left:40%;top:43%;width:26%;height:14%" aria-label="变温空间"></button>
          <button class="hotspot" data-info="freezerActual" style="left:41%;top:58%;width:28%;height:31%" aria-label="冷冻室"></button>

          <!-- 引线信息卡 -->
          <button class="chip" style="left:1.5%;top:10%" data-info="fridgeActual">
            <span class="zone">冷藏室 ${alarmFridge ? '<span class="alarm-dot" title="冷藏室门未关"></span>' : ""}</span>
            <span class="val">${fridgeActual}<small>°C</small></span>
            <span class="set">设定 ${fridgeSet}°C
              <span class="edit" data-info="fridgeSet" title="调整设定温度">✎</span>
            </span>
          </button>
          <button class="chip" style="left:1.5%;top:42%" data-info="variation">
            <span class="zone">变温空间 ${alarmVariation ? '<span class="alarm-dot" title="变温室门未关"></span>' : ""}</span>
            <span class="val" style="font-size:16px">${variation}</span>
          </button>
          <button class="chip" style="left:1.5%;top:74%" data-info="freezerActual">
            <span class="zone">冷冻室 ${alarmFreezer ? '<span class="alarm-dot" title="冷冻室门未关"></span>' : ""}</span>
            <span class="val">${freezerActual}<small>°C</small></span>
            <span class="set">设定 ${freezerSet}°C
              <span class="edit" data-info="freezerSet" title="调整设定温度">✎</span>
            </span>
          </button>
        </div>

        <div class="controls">
          <div class="ctrl-row">
            <span class="ctrl-label"><ha-icon icon="mdi:tune" style="--mdc-icon-size:14px"></ha-icon>模式</span>
            ${WORK_MODE_CHIPS.map(
              (m) => `<button class="pill ${workMode === m ? "active" : ""}" data-mode="${m}"
                        ${online && powered ? "" : "disabled"}>${m}</button>`
            ).join("")}
            ${workMode !== "--" && !WORK_MODE_CHIPS.includes(workMode)
              ? `<span class="pill muted" style="cursor:default">${workMode}</span>` : ""}
          </div>
          <div class="ctrl-row">
            <span class="ctrl-label"><ha-icon icon="mdi:fridge-outline" style="--mdc-icon-size:14px"></ha-icon>变温</span>
            ${VARIATION_OPTIONS.map(
              (m) => `<button class="pill ${variation === m ? "active" : ""}" data-variation="${m}"
                        ${online && powered ? "" : "disabled"}>${m}</button>`
            ).join("")}
          </div>
          <div class="switch-row">
            <span class="ctrl-label" style="min-width:0">
              <ha-icon icon="mdi:shield-sun" style="--mdc-icon-size:14px"></ha-icon>除菌+净味
            </span>
            <button class="toggle ${degermingOn ? "on" : ""}" data-toggle="degerming"
              ${online && powered ? "" : "disabled"} aria-label="除菌净味开关">
              <span class="knob"></span>
            </button>
          </div>
        </div>

        <div class="footer">
          <span>压缩机 ${compressor} Hz</span>
          ${updatedText ? `<span>更新于 ${esc(updatedText)}</span>` : "<span></span>"}
        </div>
      </ha-card>
    `;
  }

  _relativeTime(date) {
    const diff = (Date.now() - date.getTime()) / 1000;
    if (diff < 60) return "刚刚";
    if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`;
    if (diff < 86400) return `${Math.floor(diff / 3600)} 小时前`;
    return `${Math.floor(diff / 86400)} 天前`;
  }

  /* ------------------------------------------------------------------ */
  /* 交互                                                                */
  /* ------------------------------------------------------------------ */

  _moreInfo(entityId) {
    if (!entityId) return;
    const ev = new Event("hass-more-info", { bubbles: true, composed: true });
    ev.detail = { entityId };
    this.dispatchEvent(ev);
  }

  _onClick(ev) {
    const infoTarget = ev.target.closest("[data-info]");
    if (infoTarget) {
      // ✎ 编辑按钮打开「设定温度」number 实体，其余打开对应展示实体
      this._moreInfo(this._config.entities[infoTarget.dataset.info]);
      return;
    }
    const modeBtn = ev.target.closest("[data-mode]");
    if (modeBtn) {
      this._callService("select", "select_option", {
        entity_id: this._config.entities.workMode,
        option: modeBtn.dataset.mode,
      });
      return;
    }
    const varBtn = ev.target.closest("[data-variation]");
    if (varBtn) {
      this._callService("select", "select_option", {
        entity_id: this._config.entities.variation,
        option: varBtn.dataset.variation,
      });
      return;
    }
    const toggle = ev.target.closest("[data-toggle]");
    if (toggle) {
      this._callService("switch", "toggle", {
        entity_id: this._config.entities[toggle.dataset.toggle],
      });
    }
  }

  _callService(domain, service, data) {
    if (!this._hass) return;
    this._hass.callService(domain, service, data);
  }
}

/* -------------------------------------------------------------------- */
/* 可视化编辑器                                                          */
/* -------------------------------------------------------------------- */

class HisenseFridgeCardEditor extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = null;
    this._hass = null;
  }

  set hass(hass) {
    this._hass = hass;
  }

  set config(config) {
    this._config = { ...config };
    this._render();
  }

  _render() {
    const c = this._config || {};
    const ents = c.entities || {};
    const fields = [
      ["name_prefix", "实体名前缀", c.name_prefix || "hai_xin_bing_xiang", "如 hai_xin_bing_xiang，自动拼出全部默认实体"],
      ["name", "卡片标题", c.name || "", "留空自动取设备名"],
      ["image", "示意图地址", c.image || "/hisense/hisense-fridge.png", ""],
    ];
    const entFields = [
      ["fridgeActual", "冷藏实际温度"],
      ["fridgeSet", "冷藏设定温度"],
      ["freezerActual", "冷冻实际温度"],
      ["freezerSet", "冷冻设定温度"],
      ["variation", "变温空间"],
      ["workMode", "工作模式"],
      ["degerming", "除菌净味开关"],
      ["power", "运行状态"],
      ["online", "云连接状态"],
      ["compressor", "压缩机频率"],
      ["updated", "上次数据更新"],
      ["alarmFridgeDoor", "告警-冷藏门未关"],
      ["alarmFreezerDoor", "告警-冷冻门未关"],
      ["alarmVariationDoor", "告警-变温室门未关"],
    ];
    const defaults = defaultEntities(c.name_prefix);
    this.shadowRoot.innerHTML = `
      <style>
        .wrap { padding: 12px; display: flex; flex-direction: column; gap: 10px; }
        label { display: flex; flex-direction: column; gap: 4px; font-size: 13px; }
        label span.tip { font-size: 11px; opacity: 0.55; }
        input {
          padding: 8px 10px; border-radius: 6px; border: 1px solid var(--divider-color, #ddd);
          background: var(--card-background-color, #fff); color: var(--primary-text-color, #111);
          font: inherit; font-size: 13px; width: 100%; box-sizing: border-box;
        }
        h4 { margin: 6px 0 0; font-size: 13px; }
        .hint { font-size: 11px; opacity: 0.55; }
      </style>
      <div class="wrap">
        ${fields.map(
          ([key, label, val, tip]) => `
          <label><span>${label}</span>
            <input data-key="${key}" value="${esc(val)}" />
            ${tip ? `<span class="tip">${tip}</span>` : ""}
          </label>`
        ).join("")}
        <h4>实体覆盖（留空使用前缀默认值）</h4>
        ${entFields.map(
          ([key, label]) => `
          <label><span>${label}</span>
            <input data-ent="${key}" value="${esc(ents[key] || defaults[key] || "")}" placeholder="${esc(defaults[key] || "")}" />
          </label>`
        ).join("")}
        <span class="hint">修改前缀后下方实体默认值会随之刷新，可再逐项覆盖。</span>
      </div>
    `;
    this.shadowRoot.querySelectorAll("input[data-key]").forEach((input) => {
      input.addEventListener("change", () => this._update({ [input.dataset.key]: input.value }));
    });
    this.shadowRoot.querySelectorAll("input[data-ent]").forEach((input) => {
      input.addEventListener("change", () => {
        const entities = { ...(this._config.entities || {}), [input.dataset.ent]: input.value.trim() };
        this._update({ entities });
      });
    });
  }

  _update(patch) {
    this._config = { ...this._config, ...patch };
    // 前缀变了则重建默认实体表（保留已有覆盖）
    if (patch.name_prefix !== undefined) {
      const overrides = {};
      for (const [k, v] of Object.entries(this._config.entities || {})) {
        if (v && v !== defaultEntities(patch.name_prefix)[k]) overrides[k] = v;
      }
      this._config.entities = { ...defaultEntities(patch.name_prefix), ...overrides };
      this._render();
    }
    const ev = new Event("config-changed", { bubbles: true, composed: true });
    ev.detail = { config: this._config };
    this.dispatchEvent(ev);
  }
}

customElements.define(CARD_NAME, HisenseFridgeCard);

// 卡片选择器（编辑仪表盘时的「手动卡片」列表）
window.customCards = window.customCards || [];
window.customCards.push({
  type: CARD_NAME,
  name: "海信冰箱卡片",
  description: "HisenseHA 集成自带：冰箱分区温度可视化 + 模式/除菌/变温控制",
  preview: true,
  configurable: true,
});

console.info(`%c ${CARD_NAME.toUpperCase()} %c 1.0.0 `, "color:white;background:#03a9f4;", "");
