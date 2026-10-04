import { useCallback, useEffect, useState } from "react";
import "./App.css";
import Overview from "./Overview.jsx";

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

const DEFAULT_DEVICE_ID = "device01";
const ALERT_THRESHOLD = 300;
const MAX_HISTORY_STEP_SECONDS = 60;

const SCENARIOS = [
    {
        key: "NORMAL",
        emoji: "🌿",
        title: "Normal",
        subtitle: "No flow + no leak",
        payload: {
            water_flow: 0,
            human_present: 0,
            water_detected: 0,
            alert: 0,
            status: "NORMAL",
            running_duration_sec: 0,
            flow_rate_lpm: 0,
        },
    },
    {
        key: "NORMAL_FLOW",
        emoji: "🚰",
        title: "Normal Flow",
        subtitle: "Flow + human present",
        payload: {
            water_flow: 1,
            human_present: 1,
            water_detected: 0,
            alert: 0,
            status: "NORMAL_FLOW",
            running_duration_sec: 0,
            flow_rate_lpm: 0.2,
        },
    },
    {
        key: "WARNING",
        emoji: "🌤️",
        title: "Warning",
        subtitle: "Flow + no human + short duration",
        payload: {
            water_flow: 1,
            human_present: 0,
            water_detected: 0,
            alert: 0,
            status: "WARNING",
            running_duration_sec: 120,
            flow_rate_lpm: 0.3,
        },
    },
    {
        key: "WASTAGE_ALERT",
        emoji: "🚨",
        title: "Alert",
        subtitle: "Flow + no human + long duration",
        payload: {
            water_flow: 1,
            human_present: 0,
            water_detected: 0,
            alert: 1,
            status: "WASTAGE_ALERT",
            running_duration_sec: 310,
            flow_rate_lpm: 0.4,
        },
    },
    {
        key: "LEAK",
        emoji: "💧",
        title: "Leak",
        subtitle: "FC-37 detects water only",
        payload: {
            water_flow: 0,
            human_present: 0,
            water_detected: 1,
            alert: 0,
            status: "LEAK",
            running_duration_sec: 0,
            flow_rate_lpm: 0,
        },
    },
    {
        key: "CRITICAL",
        emoji: "🔥",
        title: "Critical",
        subtitle: "Flow + FC-37 detects water",
        payload: {
            water_flow: 1,
            human_present: 0,
            water_detected: 1,
            alert: 1,
            status: "CRITICAL",
            running_duration_sec: 0,
            flow_rate_lpm: 0.4,
        },
    },
];

const LOGIC_RULES = [
    {
        status: "NORMAL",
        condition: "No flow + no leak",
        meaning: "System idle",
        led: "Green",
        buzzer: "Off",
        notify: "No",
    },
    {
        status: "NORMAL_FLOW",
        condition: "Flow + human present",
        meaning: "Normal water use",
        led: "Blue",
        buzzer: "Off",
        notify: "No",
    },
    {
        status: "WARNING",
        condition: "Flow + no human + short duration",
        meaning: "Unattended flow",
        led: "Yellow",
        buzzer: "Off",
        notify: "No",
    },
    {
        status: "WASTAGE_ALERT",
        condition: "Flow + no human + long duration",
        meaning: "Possible forgotten tap",
        led: "Red",
        buzzer: "Intermittent",
        notify: "Yes",
    },
    {
        status: "LEAK",
        condition: "FC-37 detects water only",
        meaning: "Local water contact",
        led: "White",
        buzzer: "Slow beep",
        notify: "No",
    },
    {
        status: "CRITICAL",
        condition: "Flow + FC-37 detects water",
        meaning: "Possible leak or overflow",
        led: "Red flashing",
        buzzer: "Continuous",
        notify: "Yes",
    },
];

function toBool(value) {
    return value === 1 || value === true || value === "1" || value === "true";
}

function to01(value) {
    return toBool(value) ? 1 : 0;
}

function compactHistory(items) {
    const ordered = [...items].reverse();
    const compact = [];

    for (const item of ordered) {
        const last = compact[compact.length - 1];

        if (!last || last.status !== item.status) {
            compact.push(item);
        }
    }

    return compact.reverse();
}

function formatTime(value) {
    if (!value) {
        return "—";
    }

    const date = typeof value === "number" ? new Date(value * 1000) : new Date(value);

    return date.toLocaleTimeString("en-AU", {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: false,
    });
}

function formatDateTime(value) {
    if (!value) {
        return "—";
    }

    const date = typeof value === "number" ? new Date(value * 1000) : new Date(value);

    return date.toLocaleString("en-AU", {
        month: "short",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: false,
    });
}

function formatDurationSeconds(seconds) {
    const safeSeconds = Math.max(
        0,
        Math.round(Number(seconds || 0)),
    );

    if (safeSeconds < 60) {
        return `${safeSeconds}s`;
    }

    const minutes = Math.floor(safeSeconds / 60);
    const remainingSeconds = safeSeconds % 60;

    return `${minutes}m ${remainingSeconds}s`;
}

function deriveStatus(
    waterFlow,
    humanPresent,
    waterDetected,
    duration,
    backendStatus,
) {
    if (backendStatus) {
        return backendStatus;
    }

    if (waterFlow && waterDetected) {
        return "CRITICAL";
    }

    if (!waterFlow && waterDetected) {
        return "LEAK";
    }

    if (
        waterFlow &&
        !humanPresent &&
        duration >= ALERT_THRESHOLD
    ) {
        return "WASTAGE_ALERT";
    }

    if (waterFlow && !humanPresent) {
        return "WARNING";
    }

    if (waterFlow && humanPresent) {
        return "NORMAL_FLOW";
    }

    return "NORMAL";
}

function getStatusMeta(status) {
    const map = {
        NORMAL: {
            label: "NORMAL",
            className: "normal",
            emoji: "🌿",
            title: "Normal",
            message: "No water flow or local water contact detected.",
            led: "Green",
            ledClass: "led-green",
            buzzer: "Off",
            notify: "No",
            color: "#22c55e",
        },

        NORMAL_FLOW: {
            label: "NORMAL_FLOW",
            className: "normal-flow",
            emoji: "🚰",
            title: "Normal water use",
            message: "Water is flowing while a person is present.",
            led: "Blue",
            ledClass: "led-blue",
            buzzer: "Off",
            notify: "No",
            color: "#0ea5e9",
        },

        WARNING: {
            label: "WARNING",
            className: "warning",
            emoji: "🌤️",
            title: "Unattended flow",
            message: "Water is flowing while no person is detected.",
            led: "Yellow",
            ledClass: "led-yellow",
            buzzer: "Off",
            notify: "Yes",
            color: "#f59e0b",
        },

        WASTAGE_ALERT: {
            label: "WASTAGE_ALERT",
            className: "alert",
            emoji: "🚨",
            title: "Possible forgotten tap",
            message: "Unattended water flow reached the alert threshold.",
            led: "Red",
            ledClass: "led-red",
            buzzer: "Intermittent",
            notify: "Yes",
            color: "#f43f5e",
        },

        LEAK: {
            label: "LEAK",
            className: "leak",
            emoji: "💧",
            title: "Water contact detected",
            message: "FC-37 detected water without measurable flow.",
            led: "White",
            ledClass: "led-white",
            buzzer: "Slow beep",
            notify: "Yes",
            color: "#38bdf8",
        },

        CRITICAL: {
            label: "CRITICAL",
            className: "critical",
            emoji: "🔥",
            title: "Leak or overflow risk",
            message: "Water flow and local water contact were detected together.",
            led: "Red flashing",
            ledClass: "led-red flashing",
            buzzer: "Continuous",
            notify: "Yes",
            color: "#ef4444",
        },
    };

    return (
        map[status] ?? {
            label: "WAITING",
            className: "waiting",
            emoji: "⏳",
            title: "Waiting for data",
            message: "Run a simulation or connect a device.",
            led: "—",
            ledClass: "led-off",
            buzzer: "—",
            notify: "—",
            color: "#94a3b8",
        }
    );
}

function getEventMessage(item) {
    const status = item.status;

    if (status === "NORMAL") {
        return {
            event: "Back to normal",
            summary: "No flow or water contact detected",
            action: "Monitoring",
        };
    }

    if (status === "NORMAL_FLOW") {
        return {
            event: "Normal water use",
            summary: "Water is flowing while a person is present",
            action: "No action",
        };
    }

    if (status === "WARNING") {
        return {
            event: "Unattended flow",
            summary: "Water is flowing while no person is detected",
            action: "Checking duration",
        };
    }

    if (status === "WASTAGE_ALERT") {
        return {
            event: "Forgotten tap alert",
            summary: "Unattended flow reached the time threshold",
            action: "Alert created",
        };
    }

    if (status === "LEAK") {
        return {
            event: "Water contact detected",
            summary: "FC-37 detected water without measurable flow",
            action: "Contact time recorded",
        };
    }

    if (status === "CRITICAL") {
        return {
            event: "Critical condition",
            summary: "Flow and local water contact detected together",
            action: "Alert created",
        };
    }

    return {
        event: "Unknown event",
        summary: "Check the latest sensor values",
        action: "Review data",
    };
}

function getAlertMessage(item) {
    const status = item.status ?? item.alert_type;

    if (status === "WASTAGE_ALERT") {
        return {
            alert: "Forgotten tap alert",
            detail: "Unattended flow reached the alert threshold",
            action: item.notified
                ? "Notification sent"
                : "Alert recorded",
        };
    }

    if (status === "CRITICAL") {
        return {
            alert: "Critical leak alert",
            detail: "Flow and local water contact were detected together",
            action: item.notified
                ? "Notification sent"
                : "Alert recorded",
        };
    }

    return {
        alert: "System alert",
        detail: "An alert event was created",
        action: item.notified
            ? "Notification sent"
            : "Alert recorded",
    };
}

function isMeasuredFlowWasteStatus(status) {
    return (
        status === "WARNING" ||
        status === "WASTAGE_ALERT" ||
        status === "CRITICAL"
    );
}

function getHistoryStepSystemSeconds(
    currentItem,
    nextItem,
) {
    let elapsedRealSeconds = nextItem
        ? Number(nextItem.timestamp) -
          Number(currentItem.timestamp)
        : 0;

    if (
        !Number.isFinite(elapsedRealSeconds) ||
        elapsedRealSeconds <= 0
    ) {
        elapsedRealSeconds = 0;
    }

    if (elapsedRealSeconds > MAX_HISTORY_STEP_SECONDS) elapsedRealSeconds = 0;

    return elapsedRealSeconds;
}

function calculateSessionBreakdown(items) {
    const ordered = [...items]
        .filter((item) => item.timestamp)
        .sort(
            (a, b) =>
                Number(a.timestamp) -
                Number(b.timestamp),
        );

    let measuredWasteLitres = 0;
    let leakContactSeconds = 0;

    for (
        let index = 0;
        index < ordered.length;
        index++
    ) {
        const item = ordered[index];
        const nextItem = ordered[index + 1];
        const status = item.status;

        const elapsedSystemSeconds =
            getHistoryStepSystemSeconds(
                item,
                nextItem,
            );

        const elapsedSystemMinutes =
            elapsedSystemSeconds / 60;

        if (
            toBool(item.water_flow) &&
            isMeasuredFlowWasteStatus(status)
        ) {
            const flowRate = Number(
                item.flow_rate_lpm || 0,
            );

            if (flowRate > 0) {
                measuredWasteLitres +=
                    flowRate *
                    elapsedSystemMinutes;
            }
        }

        if (
            !toBool(item.water_flow) &&
            toBool(item.water_detected) &&
            status === "LEAK"
        ) {
            leakContactSeconds +=
                elapsedSystemSeconds;
        }
    }

    return {
        measuredWasteLitres,
        leakContactSeconds,
    };
}

function SensorCard({
    emoji,
    title,
    value,
    raw,
    detail,
    active,
}) {
    return (
        <article
            className={`sensor-card ${
                active ? "active" : ""
            }`}
        >
            <div className="sensor-icon">
                {emoji}
            </div>

            <div>
                <p>{title}</p>
                <h3>{value}</h3>
                <span>{detail}</span>
            </div>

            <code>{raw}</code>
        </article>
    );
}

function OutputCard({
    title,
    value,
    children,
}) {
    return (
        <article className="output-card">
            <p>{title}</p>
            <h3>{value}</h3>
            {children}
        </article>
    );
}

function EstimateCard({
    title,
    value,
    detail,
}) {
    return (
        <article className="estimate-card">
            <p>{title}</p>
            <h3>{value}</h3>
            <span>{detail}</span>
        </article>
    );
}

function App() {
    const [health, setHealth] = useState(false);
    const [devices, setDevices] = useState([]);
    const [analytics, setAnalytics] = useState({});
    const [system, setSystem] = useState({});
    const [selectedDevice, setSelectedDevice] =
        useState("");

    const [live, setLive] = useState(null);
    const [history, setHistory] = useState([]);
    const [alerts, setAlerts] = useState([]);

    const [lastCheck, setLastCheck] = useState(null);
    const [error, setError] = useState("");
    const [loading, setLoading] = useState(false);
    const [scenarioBusy, setScenarioBusy] =
        useState("");

    const [showRaw, setShowRaw] = useState(false);

    const loadDashboard = useCallback(
        async ({ showLoading = false } = {}) => {
            if (showLoading) {
                setLoading(true);
            }

            setError("");

            try {
                const healthRes = await fetch(
                    `${API_BASE}/health`,
                );

                setHealth(healthRes.ok);
                const systemRes = await fetch(`${API_BASE}/api/system`);
                if (systemRes.ok) setSystem(await systemRes.json());

                const devicesRes = await fetch(
                    `${API_BASE}/api/devices`,
                );

                const devicesData =
                    devicesRes.ok
                        ? await devicesRes.json()
                        : [];

                setDevices(devicesData);
                const analyticsResponses = await Promise.all(["summary", "daily", "devices", "weekly", `devices/${selectedDevice || DEFAULT_DEVICE_ID}`].map(path => fetch(`${API_BASE}/api/analytics/${path}`)));
                if (analyticsResponses.every(response => response.ok)) {
                    const [summary, daily, byDevice, weekly, device] = await Promise.all(analyticsResponses.map(response => response.json()));
                    setAnalytics({summary, daily, byDevice, weekly, device});
                }

                const currentDevice =
                    selectedDevice ||
                    devicesData?.[0]?.device_id ||
                    DEFAULT_DEVICE_ID;

                if (!selectedDevice) {
                    setSelectedDevice(
                        currentDevice,
                    );
                }

                const [
                    liveRes,
                    historyRes,
                    alertRes,
                ] = await Promise.all([
                    fetch(
                        `${API_BASE}/api/devices/${currentDevice}/live`,
                    ),
                    fetch(
                        `${API_BASE}/api/devices/${currentDevice}/history?limit=160`,
                    ),
                    fetch(
                        `${API_BASE}/api/alerts?device_id=${currentDevice}&limit=10`,
                    ),
                ]);

                if (!liveRes.ok) setLive(null);
                if (liveRes.ok) {
                    setLive(
                        await liveRes.json(),
                    );
                }

                if (historyRes.ok) {
                    setHistory(
                        await historyRes.json(),
                    );
                }

                if (alertRes.ok) {
                    setAlerts(
                        await alertRes.json(),
                    );
                }

                setLastCheck(new Date());
            } catch (err) {
                setHealth(false);

                setError(
                    "Cannot connect to the backend.",
                );

                console.error(err);
            } finally {
                if (showLoading) {
                    setLoading(false);
                }
            }
        },
        [selectedDevice],
    );

    useEffect(() => {
        const firstLoadTimer =
            window.setTimeout(() => {
                void loadDashboard();
            }, 0);

        const intervalTimer =
            window.setInterval(() => {
                void loadDashboard();
            }, 10000);

        return () => {
            window.clearTimeout(
                firstLoadTimer,
            );

            window.clearInterval(
                intervalTimer,
            );
        };
    }, [loadDashboard]);

    useEffect(() => {
        if (!selectedDevice) {
            return undefined;
        }

        const wsProtocol =
            window.location.protocol === "https:"
                ? "wss:"
                : "ws:";

        const wsOrigin = API_BASE
            ? API_BASE.replace(/^http/, "ws")
            : `${wsProtocol}//${window.location.host}`;

        let socket;
        let reconnectTimer;
        let closedByEffect = false;

        function connect() {
            socket = new WebSocket(
                `${wsOrigin}/ws/dashboard`,
            );

            socket.onmessage = () => {
                void loadDashboard();
            };

            socket.onclose = () => {
                if (!closedByEffect) {
                    reconnectTimer =
                        window.setTimeout(
                            connect,
                            3000,
                        );
                }
            };

            socket.onerror = () => {
                socket.close();
            };
        }

        connect();

        return () => {
            closedByEffect = true;

            window.clearTimeout(
                reconnectTimer,
            );

            socket?.close();
        };
    }, [selectedDevice, loadDashboard]);

    const latest =
        live ?? history?.[0] ?? {};

    const waterFlow = toBool(
        latest.water_flow,
    );

    const humanPresent = toBool(
        latest.human_present,
    );

    const waterDetected = toBool(
        latest.water_detected,
    );

    const alert = toBool(
        latest.alert,
    );

    const duration = Number(
        latest.running_duration_sec ?? 0,
    );

    const flowRate = Number(
        latest.flow_rate_lpm ?? 0,
    );

    const status = deriveStatus(
        waterFlow,
        humanPresent,
        waterDetected,
        duration,
        latest.status,
    );

    const meta = status === "OFFLINE" ? {label: "OFFLINE", title: "Device offline", message: "No recent telemetry. Check power and connectivity.", color: "#94a3b8", led: "Off", buzzer: "Off", notify: "Yes"} : getStatusMeta(status);

    const currentRule = LOGIC_RULES.find(
        (rule) => rule.status === status,
    );

    const displayHistory =
        compactHistory(history).slice(0, 5);

    const sessionBreakdown = calculateSessionBreakdown(history);
    const liveMeasuredWaste = sessionBreakdown.measuredWasteLitres;
    const totalMeasuredWaste = Number(analytics.device?.total_wasted_litres || 0);

    const demoAllowed = system.demo_enabled && selectedDevice === system.demo_device_id;

    const durationMinutes =
        duration / 60;

    async function runScenario(scenario) {
        setScenarioBusy(scenario.key);
        setError("");

        try {
            const response = await fetch(
                `${API_BASE}/api/demo/devices/${selectedDevice}/scenario/${scenario.key === "WASTAGE_ALERT" ? "ALERT" : scenario.key}`,
                {
                    method: "POST",
                },
            );

            if (!response.ok) {
                throw new Error(
                    `Simulation failed: ${response.status}`,
                );
            }

            await loadDashboard();
        } catch (err) {
            setError(
                "Simulation failed. Check the backend.",
            );

            console.error(err);
        } finally {
            setScenarioBusy("");
        }
    }
    async function resetToNormal() {
        setScenarioBusy("RESET");
        setError("");

        try {
            const response = await fetch(
                `${API_BASE}/api/demo/devices/${selectedDevice}/reset`,
                {
                    method: "POST",
                },
            );

            if (!response.ok) {
                throw new Error(
                    `Reset failed: ${response.status}`,
                );
            }

            await loadDashboard();
        } catch (err) {
            setError(
                "Reset failed. Check the backend.",
            );

            console.error(err);
        } finally {
            setScenarioBusy("");
        }
    }
    return (
        <main className="dashboard-shell">
            <div className="sunny-background">
                <div className="blob blob-a" />
                <div className="blob blob-b" />
                <div className="blob blob-c" />
            </div>

            <section className="hero">
                <div>
                    <p className="mini-label">
                        Real-Time Water Leakage and Wastage Monitoring
                    </p>

                    <h1>
                        HydroGuard
                    </h1>

                    <p className="hero-subtitle">
                        Monitor water flow, presence,
                        leak signals and alerts in real
                        time.
                    </p>
                </div>

                <div className="hero-actions">
                    <div
                        className={`health-pill ${
                            health
                                ? "online"
                                : "offline"
                        }`}
                    >
                        <span />

                        {health
                            ? "Backend Online"
                            : "Backend Offline"}
                    </div>

                    <select
                        value={selectedDevice}
                        onChange={(event) =>
                            setSelectedDevice(
                                event.target.value,
                            )
                        }
                    >
                        {devices.length === 0 ? (
                            <option
                                value={
                                    DEFAULT_DEVICE_ID
                                }
                            >
                                {
                                    DEFAULT_DEVICE_ID
                                }
                            </option>
                        ) : (
                            devices.map(
                                (device) => (
                                    <option
                                        key={
                                            device.device_id
                                        }
                                        value={
                                            device.device_id
                                        }
                                    >
                                        {
                                            device.device_id
                                        }
                                    </option>
                                ),
                            )
                        )}
                    </select>

                    <button
                        type="button"
                        onClick={() =>
                            loadDashboard({
                                showLoading: true,
                            })
                        }
                        disabled={loading}
                    >
                        {loading
                            ? "Refreshing..."
                            : "Refresh"}
                    </button>
                </div>
            </section>

            <Overview data={analytics} devices={devices} selectedDevice={selectedDevice} onSelect={deviceId => { setLive(null); setHistory([]); setSelectedDevice(deviceId); }} />



            {error ? (
                <div className="error-banner">
                    {error}
                </div>
            ) : null}

            <section
                className={`status-showcase ${meta.className}`}
            >
                <div className="status-main">
                    <div className="big-emoji">
                        {meta.emoji}
                    </div>

                    <div>
                        <span
                            className="status-chip"
                            style={{
                                backgroundColor:
                                    meta.color,
                            }}
                        >
                            {meta.label}
                        </span>

                        <h2>
                            {meta.title}
                        </h2>

                        <p>
                            {meta.message}
                        </p>
                    </div>
                </div>

                <div className="status-side">
                    <div>
                        <span>
                            Last device message
                        </span>

                        <strong>
                            {formatTime(
                                latest.last_seen ??
                                    latest.timestamp,
                            )}
                        </strong>
                    </div>

                    <div>
                        <span>
                            Dashboard check
                        </span>

                        <strong>
                            {formatTime(
                                lastCheck,
                            )}
                        </strong>
                    </div>

                    <div>
                        <span>
                            Current rule
                        </span>

                        <strong>
                            {currentRule?.condition ??
                                "Waiting"}
                        </strong>
                    </div>
                </div>
            </section>

            <section className="grid four">
                <SensorCard
                    emoji="🚰"
                    title="Flow Sensor"
                    value={
                        waterFlow
                            ? "Flowing"
                            : "No flow"
                    }
                    raw={`water_flow=${to01(
                        waterFlow,
                    )}`}
                    detail={`${flowRate.toFixed(
                        2,
                    )} L/min`}
                    active={waterFlow}
                />

                <SensorCard
                    emoji="🧍"
                    title="Human Presence"
                    value={
                        humanPresent
                            ? "Present"
                            : "Not detected"
                    }
                    raw={`human_present=${to01(
                        humanPresent,
                    )}`}
                    detail="LD2410C input"
                    active={humanPresent}
                />

                <SensorCard
                    emoji="💧"
                    title="FC-37 Water Sensor"
                    value={
                        waterDetected
                            ? "Water detected"
                            : "Dry"
                    }
                    raw={`water_detected=${to01(
                        waterDetected,
                    )}`}
                    detail="Water contact input"
                    active={waterDetected}
                />

                <SensorCard
                    emoji="⏱️"
                    title="Running Duration"
                    value={`${duration}s`}
                    raw={`alert=${to01(alert)}`}
                    detail={`Alert threshold: ${system.unattended_threshold_sec || ALERT_THRESHOLD}s`}
                    active={
                        duration >=
                        ALERT_THRESHOLD
                    }
                />
            </section>

            <section className="grid three">
                <OutputCard
                    title="LED Output"
                    value={meta.led}
                >
                    <div
                        className={`led-dot ${meta.ledClass}`}
                    />
                </OutputCard>

                <OutputCard
                    title="Buzzer Output"
                    value={meta.buzzer}
                >
                    <span className="small-note">
                        Local warning
                    </span>
                </OutputCard>

                <OutputCard
                    title="Notify User"
                    value={meta.notify}
                >
                    <span className="small-note">
                        Warnings, wastage, leaks and offline events
                    </span>
                </OutputCard>
            </section>

            <section className="panel estimate-panel">
                <div className="panel-header">
                    <div>
                        <p className="mini-label">
                            Water Usage
                        </p>

                        <h2>
                            Estimated Water Waste
                        </h2>
                    </div>

                    <p>
                        Flow rate is used for litre
                        estimates. FC-37-only events are
                        recorded as contact time.
                    </p>
                </div>

                <div className="estimate-grid">
                    <EstimateCard
                        title="Flow rate"
                        value={`${flowRate.toFixed(
                            2,
                        )} L/min`}
                        detail="YF-S201 reading"
                    />

                    <EstimateCard
                        title="Recent measured waste"
                        value={`${liveMeasuredWaste.toFixed(
                            2,
                        )} L`}
                        detail={`${durationMinutes.toFixed(
                            2,
                        )} min`}
                    />

                    <EstimateCard
                        title="Total measured waste"
                        value={`${totalMeasuredWaste.toFixed(
                            2,
                        )} L`}
                        detail="Stored device total"
                    />

                    <EstimateCard
                        title="Leak contact time"
                        value={formatDurationSeconds(
                            sessionBreakdown.leakContactSeconds,
                        )}
                        detail="FC-37 contact duration"
                    />
                </div>

                <div className="estimate-note">
                    <strong>
                        Formula:
                    </strong>{" "}
                    water = flow rate × duration / 60.
                    FC-37 contact is not converted to
                    litres because it does not measure
                    flow.
                </div>
            </section>

            <section className="panel">
                <div className="panel-header">
                    <div>
                        <p className="mini-label">
                            Demo Mode
                        </p>

                        <h2>
                            Simulation Control
                        </h2>
                    </div>

                    <p>
                        Demo controls are available for the configured demo device.
                        Use the MQTT simulator for other locations.
                    </p>
                </div>

                <div className="scenario-grid">
                    <button
                        type="button"
                        className="scenario-button scenario-normal"
                        onClick={() =>
                            resetToNormal()
                        }
                        disabled={!demoAllowed || Boolean(scenarioBusy)}
                    >
                        <span>
                            ↩️
                        </span>

                        <strong>
                            Reset Normal
                        </strong>

                        <small>
                            No flow + no leak
                        </small>

                        {scenarioBusy ===
                        "RESET" ? (
                            <em>
                                Resetting...
                            </em>
                        ) : null}
                    </button>

                    {SCENARIOS.map(
                        (scenario) => (
                            <button
                                key={
                                    scenario.key
                                }
                                type="button"
                                className={`scenario-button scenario-${scenario.key.toLowerCase()}`}
                                onClick={() =>
                                    runScenario(
                                        scenario,
                                    )
                                }
                                disabled={!demoAllowed || Boolean(scenarioBusy)}
                            >
                                <span>
                                    {
                                        scenario.emoji
                                    }
                                </span>

                                <strong>
                                    {
                                        scenario.title
                                    }
                                </strong>

                                <small>
                                    {
                                        scenario.subtitle
                                    }
                                </small>

                                {scenarioBusy ===
                                scenario.key ? (
                                    <em>
                                        Sending...
                                    </em>
                                ) : null}
                            </button>
                        ),
                    )}
                </div>
            </section>

            <section className="panel">
                <div className="panel-header">
                    <div>
                        <p className="mini-label">
                            Decision Logic
                        </p>

                        <h2>
                            Condition Rules
                        </h2>
                    </div>

                    <p>
                        The active rule follows the latest
                        sensor values.
                    </p>
                </div>

                <div className="logic-table">
                    <div className="logic-row table-head">
                        <span>
                            Condition
                        </span>

                        <span>
                            Meaning
                        </span>

                        <span>
                            Status
                        </span>

                        <span>
                            LED
                        </span>

                        <span>
                            Buzzer
                        </span>

                        <span>
                            Notify
                        </span>
                    </div>

                    {LOGIC_RULES.map(
                        (rule) => (
                            <div
                                key={
                                    rule.status
                                }
                                className={`logic-row ${
                                    rule.status ===
                                    status
                                        ? "active"
                                        : ""
                                }`}
                            >
                                <span>
                                    {
                                        rule.condition
                                    }
                                </span>

                                <span>
                                    {
                                        rule.meaning
                                    }
                                </span>

                                <span className="logic-status">
                                    {
                                        rule.status
                                    }
                                </span>

                                <span>
                                    {rule.led}
                                </span>

                                <span>
                                    {
                                        rule.buzzer
                                    }
                                </span>

                                <span>
                                    {
                                        rule.notify
                                    }
                                </span>
                            </div>
                        ),
                    )}
                </div>
            </section>

            <section className="bottom-grid">
                <div className="panel">
                    <div className="panel-header compact">
                        <div>
                            <p className="mini-label">
                                Recent Events
                            </p>

                            <h2>
                                Device History
                            </h2>
                        </div>
                    </div>

                    <div className="event-list">
                        {displayHistory.length ===
                        0 ? (
                            <p className="empty">
                                No sensor history
                                yet.
                            </p>
                        ) : (
                            displayHistory.map(
                                (
                                    item,
                                    index,
                                ) => {
                                    const message =
                                        getEventMessage(
                                            item,
                                        );

                                    return (
                                        <div
                                            key={`${item.timestamp}-${item.status}-${index}`}
                                            className="event-item readable-event"
                                        >
                                            <div className="event-main">
                                                <strong>
                                                    {
                                                        message.event
                                                    }
                                                </strong>

                                                <span>
                                                    {formatDateTime(
                                                        item.timestamp,
                                                    )}
                                                </span>

                                                <p>
                                                    {
                                                        message.summary
                                                    }
                                                </p>
                                            </div>

                                            <code>
                                                {
                                                    message.action
                                                }
                                            </code>
                                        </div>
                                    );
                                },
                            )
                        )}
                    </div>
                </div>

                <div className="panel">
                    <div className="panel-header compact">
                        <div>
                            <p className="mini-label">
                                Notifications
                            </p>

                            <h2>
                                Alert History
                            </h2>
                        </div>
                    </div>

                    <div className="event-list">
                        {alerts.length === 0 ? (
                            <p className="empty">
                                No alert history
                                yet.
                            </p>
                        ) : (
                            alerts.map(
                                (
                                    item,
                                    index,
                                ) => {
                                    const message =
                                        getAlertMessage(
                                            item,
                                        );

                                    return (
                                        <div
                                            key={`${item.timestamp}-${index}`}
                                            className="event-item alert-item"
                                        >
                                            <div className="event-main">
                                                <strong>
                                                    {
                                                        message.alert
                                                    }
                                                </strong>

                                                <span>
                                                    {formatDateTime(
                                                        item.timestamp,
                                                    )}
                                                </span>

                                                <p>
                                                    {
                                                        message.detail
                                                    }
                                                </p>
                                            </div>

                                            <code>
                                                {
                                                    message.action
                                                }
                                            </code>
                                        </div>
                                    );
                                },
                            )
                        )}
                    </div>
                </div>
            </section>

            <section className="panel raw-panel">
                <button
                    type="button"
                    className="raw-toggle"
                    onClick={() =>
                        setShowRaw(
                            (value) =>
                                !value,
                        )
                    }
                >
                    {showRaw
                        ? "Hide raw data"
                        : "Show raw data"}
                </button>

                {showRaw ? (
                    <pre>
                        {JSON.stringify(
                            {
                                selectedDevice,
                                latest,
                                derived_status:
                                    status,
                                led: meta.led,
                                buzzer:
                                    meta.buzzer,
                                notify_user:
                                    meta.notify,
                                flow_rate_lpm:
                                    flowRate,
                                system_duration_sec:
                                    duration,
                                live_measured_waste_litres:
                                    Number(
                                        liveMeasuredWaste.toFixed(
                                            2,
                                        ),
                                    ),
                                total_measured_waste_litres:
                                    Number(
                                        totalMeasuredWaste.toFixed(
                                            2,
                                        ),
                                    ),
                                leak_contact_seconds:
                                    Math.round(
                                        sessionBreakdown.leakContactSeconds,
                                    ),
                                formula:
                                    "water = flow_rate_lpm * duration_seconds / 60",
                                time_scale:
                                    "Real elapsed time for volume estimates",
                            },
                            null,
                            2,
                        )}
                    </pre>
                ) : null}
            </section>
        </main>
    );
}

export default App;