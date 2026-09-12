
import React, {useEffect,useState} from "react";
import {createRoot} from "react-dom/client";
import {BarChart,Bar,XAxis,YAxis,Tooltip,ResponsiveContainer,LineChart,Line} from "recharts";
import "./style.css";

const API="http://localhost:8000";

function App(){
  const [overview,setOverview]=useState({});
  const [rows,setRows]=useState([]);
  const [selected,setSelected]=useState(null);
  const [detail,setDetail]=useState([]);
  const [redis,setRedis]=useState([]);

  useEffect(()=>{
    Promise.all([
      fetch(API+"/analytics/overview").then(r=>r.json()),
      fetch(API+"/shortages").then(r=>r.json())
    ]).then(([a,b])=>{setOverview(a);setRows(b)});
  },[]);

  const select=async r=>{
    setSelected(r);
    const d=await fetch(API+"/facility/"+r.facility_id).then(x=>x.json());
    setDetail(d);
    const rr=await fetch(API+"/redistribution/"+r.medicine_id).then(x=>x.json());
    setRedis(rr);
  };

  const chart=rows.slice(0,10).map(x=>({name:x.facility_id+"-"+x.medicine_id,score:x.risk_score}));

  return <div className="app">
    <header>
      <div>
        <h1>Regional Medicine Shortage Early Warning</h1>
        <p>Detect → Explain → Redistribute → Intervene</p>
      </div>
      <span className="badge">Synthetic Demo</span>
    </header>

    <section className="cards">
      <div><b>{overview.high_risk||0}</b><span>High risk</span></div>
      <div><b>{overview.potential_stockouts_14d||0}</b><span>≤14-day stock</span></div>
      <div><b>{overview.facilities||0}</b><span>Facilities</span></div>
      <div><b>{overview.medicines||0}</b><span>Medicines</span></div>
    </section>

    <main>
      <section className="panel">
        <h2>Emerging shortage signals</h2>
        <div className="chart"><ResponsiveContainer width="100%" height={260}>
          <BarChart data={chart}><XAxis dataKey="name"/><YAxis/><Tooltip/><Bar dataKey="score"/></BarChart>
        </ResponsiveContainer></div>
        <table>
          <thead><tr><th>Facility</th><th>Medicine</th><th>Stock days</th><th>Demand trend</th><th>Risk</th></tr></thead>
          <tbody>{rows.map((r,i)=><tr key={i} onClick={()=>select(r)}>
            <td>{r.facility_name}</td><td>{r.medicine_name}</td>
            <td>{r.days_of_stock.toFixed(1)}</td>
            <td>{(r.demand_trend*100).toFixed(0)}%</td>
            <td><span className={"risk "+r.risk_level.toLowerCase()}>{r.risk_level} {r.risk_score.toFixed(0)}</span></td>
          </tr>)}</tbody>
        </table>
      </section>

      <section className="panel">
        <h2>{selected ? selected.facility_name : "Select a facility"}</h2>
        {selected ? <>
          <p><b>{selected.medicine_name}</b> — {selected.city}</p>
          <div className="mini">
            <div>Current stock<br/><b>{selected.stock_on_hand}</b></div>
            <div>Days remaining<br/><b>{selected.days_of_stock.toFixed(1)}</b></div>
            <div>Risk score<br/><b>{selected.risk_score.toFixed(0)}/100</b></div>
            <div>Confidence<br/><b>{selected.confidence}%</b></div>
          </div>
          <h3>Shortage reasoning</h3>
          <ul>
            {selected.days_of_stock<=14 && <li>Projected stock reaches critical level within 14 days.</li>}
            {selected.demand_trend>0.1 && <li>Recent consumption is rising versus the historical baseline.</li>}
            {selected.inventory_ratio<0.45 && <li>Inventory is below the normal stock threshold.</li>}
          </ul>
          <h3>Nearby redistribution opportunities</h3>
          {redis.length ? redis.slice(0,4).map((x,i)=><div className="rec" key={i}>
            <b>{x.from_facility} → {x.to_facility}</b><br/>
            {x.distance_km} km · donor {x.donor_days_stock} days · recipient {x.recipient_days_stock} days
          </div>) : <p>No suitable donor detected in the demo data.</p>}
          <h3>Facility inventory trend</h3>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={detail}><XAxis dataKey="medicine_name"/><YAxis/><Tooltip/><Line dataKey="days_of_stock" strokeWidth={2}/></LineChart>
          </ResponsiveContainer>
        </> : <p>Click a row to inspect the signal and redistribution recommendation.</p>}
      </section>
    </main>
  </div>
}
createRoot(document.getElementById("root")).render(<App/>);
