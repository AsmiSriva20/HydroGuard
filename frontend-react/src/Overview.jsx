function Bars({ title, rows, label, value }) {
    const max = Math.max(1, ...rows.map(row => Number(row[value])));
    return <section className="panel"><h2>{title}</h2>{rows.length === 0 ? <p>No measurements yet.</p> : rows.map(row =>
        <div className="usage-row" key={row[label]}><span title={row[label]}>{row[label]}</span><meter min="0" max={max} value={row[value]} aria-label={`${row[label]}: ${Number(row[value]).toFixed(2)} litres`} /><strong>{Number(row[value]).toFixed(2)} L</strong></div>)}</section>;
}

export default function Overview({ data, devices, selectedDevice, onSelect }) {
    const summary = data.summary || {};
    const cards = [["Water used today", `${Number(summary.today_used_litres || 0).toFixed(2)} L`],
        ["Estimated waste today", `${Number(summary.today_wasted_litres || 0).toFixed(2)} L`],
        ["Active devices", summary.active_devices || 0], ["Offline devices", summary.offline_devices || 0],
        ["Active alerts", summary.active_alerts || 0], ["Leak incidents today", summary.leak_incidents_today || 0]];
    return <>
        <section className="overview-cards">{cards.map(([label, value]) => <div className="panel" key={label}><p>{label}</p><h2>{value}</h2></div>)}</section>
        <section className="panel"><h2>Monitoring locations</h2><div className="devices-scroll"><table className="devices-table"><thead><tr><th>Device</th><th>Location</th><th>Connection</th><th>State</th><th>Flow</th><th>Last seen</th><th>Alert</th></tr></thead><tbody>
            {devices.map(device => <tr key={device.device_id} className={selectedDevice === device.device_id ? "selected" : ""}><td><button onClick={() => onSelect(device.device_id)}>{device.device_name || device.device_id}</button></td><td>{device.location || device.device_id.replaceAll("_", " ")}</td><td>{device.connection_status}</td><td>{device.status || "OFFLINE"}</td><td>{device.connection_status === "ONLINE" ? `${Number(device.flow_rate_lpm || 0).toFixed(2)} L/min` : "?"}</td><td>{device.last_seen ? new Date(device.last_seen * 1000).toLocaleString() : "Never"}</td><td>{device.has_active_alert ? "Active" : "Clear"}</td></tr>)}
        </tbody></table></div>{devices.length === 0 && <p>Start the simulator or register an ESP32 to see locations.</p>}</section>
        <p className="small-note">Daily and weekly analytics use UTC dates. Select a device for its live readings and history below.</p>
        <section className="overview-charts"><Bars title="Daily water usage" rows={data.daily || []} label="day" value="used_litres" /><Bars title="Daily estimated wastage" rows={data.daily || []} label="day" value="wasted_litres" /><Bars title="Usage per device" rows={data.byDevice || []} label="device_id" value="used_litres" /><Bars title="Weekly water usage" rows={data.weekly || []} label="week" value="used_litres" /></section>
    </>;
}
