import React, {useEffect,useState} from "react";
import {createRoot} from "react-dom/client";
import {BarChart,Bar,XAxis,YAxis,Tooltip,ResponsiveContainer,LineChart,Line} from "recharts";
import "./style.css";

const API="http://localhost:8000";

const fmtCr=v=>"₹"+(v||0).toLocaleString("en-IN")+" Cr";

function App(){
  const [overview,setOverview]=useState({});
  const [rows,setRows]=useState([]);
  const [selected,setSelected]=useState(null);

  useEffect(()=>{
    Promise.all([
      fetch(API+"/analytics/overview").then(r=>r.json()),
      fetch(API+"/scrutiny").then(r=>r.json())
    ]).then(([a,b])=>{setOverview(a);setRows(b)});
  },[]);

  const select=async r=>{
    setSelected(null);
    const d=await fetch(API+"/contract/"+r.contract_id).then(x=>x.json());
    setSelected(d);
  };

  const chart=rows.slice(0,10).map(x=>({name:x.contract_id,score:x.scrutiny_score}));

  return <div className="app">
    <header>
      <div>
        <h1>Post-Award Contract Change Monitor</h1>
        <p>Compare baseline commitment → surface variation → attach evidence → route for review</p>
      </div>
      <span className="badge">Synthetic Demo</span>
    </header>

    <section className="cards">
      <div><b>{overview.high_priority||0}</b><span>High-priority review</span></div>
      <div><b>{overview.cost_overruns||0}</b><span>Cost &gt;10% above award</span></div>
      <div><b>{overview.contractor_changes||0}</b><span>Contractor substitutions</span></div>
      <div><b>{overview.evidence_gaps||0}</b><span>Missing change evidence</span></div>
    </section>

    <main>
      <section className="panel">
        <h2>Contracts requiring attention</h2>
        <div className="chart"><ResponsiveContainer width="100%" height={260}>
          <BarChart data={chart}><XAxis dataKey="name"/><YAxis/><Tooltip/><Bar dataKey="score" fill="#0a6ff5"/></BarChart>
        </ResponsiveContainer></div>
        <table>
          <thead><tr><th>Contract</th><th>Agency</th><th>Value Δ%</th><th>Slip (days)</th><th>Contractor</th><th>Evidence</th><th>Priority</th></tr></thead>
          <tbody>{rows.map((r,i)=><tr key={i} onClick={()=>select(r)}>
            <td>{r.title}<div className="sub">{r.region}</div></td>
            <td>{r.agency}</td>
            <td>{(r.cost_delta_pct>0?"+":"")+r.cost_delta_pct.toFixed(0)}%</td>
            <td>{r.schedule_delta_days}</td>
            <td>{r.contractor_changed? <span className="changed">changed</span> : r.contractor_baseline}</td>
            <td>{(r.evidence_ratio*100).toFixed(0)}%</td>
            <td><span className={"risk "+r.review_priority.toLowerCase()}>{r.review_priority} {r.scrutiny_score.toFixed(0)}</span></td>
          </tr>)}</tbody>
        </table>
      </section>

      <section className="panel">
        <h2>{selected ? selected.title : "Select a contract"}</h2>
        {selected ? <>
          <p><b>{selected.agency}</b> · {selected.region} · {selected.category}</p>
          <div className="mini">
            <div>Awarded value<br/><b>{fmtCr(selected.awarded_value_mn)}</b></div>
            <div>Approved value<br/><b>{fmtCr(selected.current_approved_value_mn)}</b></div>
            <div>Change orders<br/><b>{selected.co_count}</b></div>
            <div>Scrutiny<br/><b>{selected.scrutiny_score.toFixed(0)}/100</b></div>
          </div>
          <div className="cmp">
            <div><h4>Baseline commitment</h4>
              <p>Contractor: {selected.contractor_baseline}</p>
              <p>Planned completion: {selected.baseline_end_date}</p>
              <p>Award: {fmtCr(selected.awarded_value_mn)}</p>
            </div>
            <div className="arrow">→</div>
            <div><h4>Current status</h4>
              <p>Contractor: {selected.contractor_current}</p>
              <p>Revised completion: {selected.revised_end_date}</p>
              <p>Approved: {fmtCr(selected.current_approved_value_mn)}</p>
            </div>
          </div>
          <h3>Detected variation &amp; reasoning</h3>
          <ul>{selected.flags.length ? selected.flags.map((f,i)=><li key={i}>{f}</li>) : <li>No significant variation detected beyond normal execution adjustments.</li>}</ul>
          <h3>Change orders &amp; supporting evidence</h3>
          <table className="thin">
            <thead><tr><th>Change #</th><th>Date</th><th>Type</th><th>Description</th><th>ΔValue</th><th>Evidence</th></tr></thead>
            <tbody>{selected.changes.map((c,i)=><tr key={i}>
              <td>{c.change_id}</td><td>{c.change_date}</td><td>{c.change_type}</td>
              <td>{c.description}</td><td>{fmtCr(c.delta_value_mn)}</td>
              <td><span className={"ev "+(c.evidence_doc==="MISSING"?"missing":"ok")}>{c.evidence_doc==="MISSING"?"Missing":"On file"}</span></td>
            </tr>)}</tbody>
          </table>
          <h3>Cumulative approved value vs award</h3>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={selected.history}>
              <XAxis dataKey="month"/><YAxis/><Tooltip/>
              <Line dataKey="awarded_value_mn" name="Awarded" stroke="#777" strokeDasharray="4 4"/>
              <Line dataKey="approved_value_mn" name="Approved" stroke="#0a6ff5" strokeWidth={2}/>
            </LineChart>
          </ResponsiveContainer>
        </> : <p>Click a contract row to compare its original commitment with current project information.</p>}
      </section>
    </main>
  </div>
}
createRoot(document.getElementById("root")).render(<App/>);