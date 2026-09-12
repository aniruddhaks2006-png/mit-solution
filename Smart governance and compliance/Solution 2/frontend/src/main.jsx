import React, {useEffect,useState} from "react";
import {createRoot} from "react-dom/client";
import {BarChart,Bar,XAxis,YAxis,Tooltip,ResponsiveContainer} from "recharts";
import "./style.css";

const API="http://localhost:8011";
const fmtCr=v=>"₹"+(v||0).toLocaleString("en-IN")+" Cr";
const TYPE_COLOR={"co-bid":"#38bdf8","shared phone":"#f59e0b","shared domain":"#a78bfa","shared director":"#34d399","shared address":"#f472b6"};

function Network({vendorId,data}){
  if(!data || data.nodes.length<2) return <p className="muted">No connected parties found for this vendor.</p>;
  const {nodes,edges}=data;
  const W=560,H=340,cx=W/2,cy=H/2,pos={};
  const posOf={};
  edges.forEach(e=>{ [e.source,e.target].forEach(id=>{ if(!posOf[id]) posOf[id]=true; }); });
  nodes.forEach(n=>posOf[n.vendor_id]=true);
  const ids=Object.keys(posOf);
  ids.forEach((id,i)=>{
    const isCenter=id===vendorId;
    const depth = edges.some(e=>e.source===vendorId&&e.target===id)||edges.some(e=>e.target===vendorId&&e.source===id)?1:2;
    const n = ids.filter(other=>other!==id && (edges.some(e=>(e.source===id&&e.target===other)||(e.source===other&&e.target===id)))).length;
    const idx = ids.indexOf(id);
    const R = isCenter ? 0 : depth===1 ? 120 : 250;
    const total = Math.max(1,ids.length- (isCenter?1:0));
    const angle=(2*Math.PI*idx)/total - Math.PI/2;
    pos[id]=[cx+R*Math.cos(angle), cy+R*Math.sin(angle)];
  });
  const nameOf={};
  nodes.forEach(n=>nameOf[n.vendor_id]=n.vendor_id);
  return <svg viewBox={`0 0 ${W} ${H}`} className="net">
    {edges.map((e,i)=>{ const [x1,y1]=pos[e.source],[x2,y2]=pos[e.target];
      const c=TYPE_COLOR[e.type]||"#94a3b8";
      return <g key={i}>
        <line x1={x1} y1={y1} x2={x2} y2={y2} stroke={c} strokeWidth={Math.max(1,Math.min(6,e.strength/2))} opacity={0.85}/>
        <text x={(x1+x2)/2} y={(y1+y2)/2-6} textAnchor="middle" fontSize="9" fill={c}>{e.type}</text>
      </g>;})}
    {nodes.map(n=>{ const [x,y]=pos[n.vendor_id]; if(!x) return null;
      return <g key={n.vendor_id}>
        <circle cx={x} cy={y} r={n.central?22:14} fill={n.central?"#2563eb":"#1e293b"} stroke="#38bdf8" strokeWidth={n.central?2:1}/>
        <text x={x} y={n.central? y+36 : y+30} textAnchor="middle" fontSize="9" fill="#cbd5e1">{nameOf[n.vendor_id]}</text>
      </g>;})}
  </svg>;
}

function App(){
  const [overview,setOverview]=useState({});
  const [rows,setRows]=useState([]);
  const [selected,setSelected]=useState(null);
  const [net,setNet]=useState(null);

  useEffect(()=>{
    fetch(API+"/analytics/overview").then(r=>r.json()).then(setOverview).catch(()=>{});
    fetch(API+"/cases").then(r=>r.json()).then(setRows).catch(()=>{});
  },[]);

  const select=async r=>{
    setSelected(null); setNet(null);
    const [d,n]=await Promise.all([
      fetch(API+"/vendor/"+r.vendor_id).then(x=>x.json()),
      fetch(API+"/network/"+r.vendor_id).then(x=>x.json())
    ]);
    setSelected(d); setNet(n);
  };

  const chart=rows.slice(0,10).map(x=>({name:x.vendor_id,score:x.investigation_score}));

  return <div className="app">
    <header>
      <div>
        <h1>Procurement Anomaly &amp; Relationship Audit</h1>
        <p>Pattern discovery → relationship mapping → investigation priority (no presumptions of corruption)</p>
      </div>
      <span className="badge">Synthetic Demo</span>
    </header>

    <section className="cards">
      <div><b>{overview.high_priority||0}</b><span>High-priority cases</span></div>
      <div><b>{overview.medium_priority||0}</b><span>Medium-priority cases</span></div>
      <div><b>{overview.connected_groups||0}</b><span>Connected vendor groups</span></div>
      <div><b>{overview.split_payment_contracts||0}</b><span>Split-payment contracts</span></div>
      <div><b>{overview.tenders||0}</b><span>Tenders</span></div>
      <div><b>{overview.vendors||0}</b><span>Vendors</span></div>
    </section>

    <main>
      <section className="panel">
        <h2>Vendors flagged for investigation</h2>
        <div className="chart"><ResponsiveContainer width="100%" height={240}>
          <BarChart data={chart}><XAxis dataKey="name"/><YAxis/><Tooltip/><Bar dataKey="score" fill="#0a6ff5"/></BarChart>
        </ResponsiveContainer></div>
        <table>
          <thead><tr><th>Vendor</th><th>Wins/Tenders</th><th>Connected</th><th>Co-bid</th><th>Price gap</th><th>Category share</th><th>Priority</th></tr></thead>
          <tbody>{rows.map((r,i)=><tr key={i} onClick={()=>select(r)}>
            <td>{r.name}<div className="sub">{r.vendor_id} · {r.city}</div></td>
            <td>{r.wins}/{r.bids}</td>
            <td>{r.connected}</td>
            <td>{r.max_co_bid}</td>
            <td>{r.price_gap>0?"+"+r.price_gap.toFixed(0):r.price_gap.toFixed(0)}%</td>
            <td>{(r.category_share*100).toFixed(0)}%</td>
            <td><span className={"risk "+r.review_priority.toLowerCase()}>{r.review_priority} {r.investigation_score.toFixed(0)}</span></td>
          </tr>)}</tbody>
        </table>
      </section>

      <section className="panel">
        <h2>{selected ? selected.name : "Select a vendor"}</h2>
        {selected ? <>
          <p><b>{selected.vendor_id}</b> · {selected.city} · registered {selected.reg_year}</p>
          <div className="mini">
            <div>Wins<br/><b>{selected.wins}</b></div>
            <div>Bids<br/><b>{selected.bids}</b></div>
            <div>Connected<br/><b>{selected.connected}</b></div>
            <div>Investigation score<br/><b>{selected.investigation_score.toFixed(0)}/100</b></div>
          </div>
          <h3>Why this vendor is flagged</h3>
          <ul>{selected.reasons.length? selected.reasons.map((r,i)=><li key={i}>{r}</li>) : <li>No significant pattern surfaced — this is a control case shown for comparison.</li>}</ul>

          <h3>Relationship network</h3>
          <Network vendorId={selected.vendor_id} data={net}/>

          <h3>Relationships ({selected.relationships_detail.length})</h3>
          <table className="thin">
            <thead><tr><th>Partner</th><th>Type</th><th>Strength</th></tr></thead>
            <tbody>{selected.relationships_detail.slice(0,12).map((r,i)=><tr key={i}>
              <td>{r.partner}</td>
              <td style={{color:TYPE_COLOR[r.relation_type]||"#cbd5e1"}}>{r.relation_type}</td>
              <td>{r.strength}</td>
            </tr>)}</tbody>
          </table>

          <h3>Awarded tenders ({selected.wins_detail.length})</h3>
          <table className="thin">
            <thead><tr><th>Tender</th><th>Category</th><th>Buyer</th><th>Award</th><th>Est</th></tr></thead>
            <tbody>{selected.wins_detail.slice(0,10).map((w,i)=><tr key={i}>
              <td>{w.tender_id}</td><td>{w.category}</td><td>{w.buyer}</td>
              <td>{fmtCr(w.award_value_mn)}</td><td>{fmtCr(w.est_value_mn)}</td>
            </tr>)}</tbody>
          </table>
        </> : <p>Click a vendor row to inspect its patterns, relationships and supporting evidence.</p>}
      </section>
    </main>
  </div>
}
createRoot(document.getElementById("root")).render(<App/>);