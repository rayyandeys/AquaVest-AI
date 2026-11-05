import {useCallback,useEffect,useState} from 'react';
import {NavLink,Route,Routes,useLocation} from 'react-router-dom';
import {Waves,LayoutDashboard,BriefcaseBusiness,ChartNoAxesCombined,Star,ArrowLeftRight,Sparkles,Settings as SettingsIcon,Bell,ChevronLeft,Menu,X,LogOut} from 'lucide-react';
import {StockSearch} from './components/StockSearch';
import {TransactionModal} from './components/TransactionModal';
import {AuthScreen,type Account} from './components/AuthScreen';
import {Dashboard} from './pages/Dashboard';
import {StockDetail} from './pages/StockDetail';
import {MarketsPage,Watchlist,Transactions,Insights,Settings} from './pages/OtherPages';
import {api,errorMessage} from './services/api';
import {disclaimer} from './utils/format';

const links=[['/','Overview',LayoutDashboard],['/portfolio','Portfolio',BriefcaseBusiness],['/markets','Markets',ChartNoAxesCombined],['/watchlist','Watchlist',Star],['/transactions','Transactions',ArrowLeftRight],['/insights','AI Insights',Sparkles],['/settings','Settings',SettingsIcon]] as const;

export default function App(){
 const [account,setAccount]=useState<Account|null>(null);const [checking,setChecking]=useState(true);
 const [revision,setRevision]=useState(0);const [modal,setModal]=useState<string|null>(null);const [toast,setToast]=useState('');
 const [collapsed,setCollapsed]=useState(false);const [notifications,setNotifications]=useState(false);const [closing,setClosing]=useState<string|null>(null);const [busy,setBusy]=useState(false);
 const location=useLocation();const notify=useCallback((s:string)=>setToast(s),[]);const close=useCallback(()=>setModal(null),[]);const refresh=()=>setRevision(r=>r+1);
 useEffect(()=>{api.get<Account>('/auth/me').then(r=>setAccount(r.data)).catch(()=>setAccount(null)).finally(()=>setChecking(false))},[]);
 useEffect(()=>{if(toast){const t=setTimeout(()=>setToast(''),4500);return()=>clearTimeout(t)}},[toast]);useEffect(()=>{window.scrollTo(0,0)},[location.pathname]);
 async function logout(){try{await api.post('/auth/logout')}finally{setAccount(null);setRevision(0)}}
 if(checking)return <div className="auth-wait">Loading your secure workspace…</div>;
 if(!account)return <AuthScreen onAuth={setAccount}/>;
 const initials=account.name.trim().split(/\s+/).slice(0,2).map(x=>x[0]).join('').toUpperCase();
 return <div className={'app '+(collapsed?'collapsed':'')}><div className="ambient ambient-one"/><div className="ambient ambient-two"/><aside className="sidebar">
  <NavLink className="brand" to="/"><span className="brand-mark"><Waves size={25}/></span><span>AquaVest<small>AI PORTFOLIO INTELLIGENCE</small></span></NavLink><div className="sidebar-label">WORKSPACE</div>
  <nav>{links.map(([url,label,Icon])=><NavLink end={url==='/'} to={url} key={url} title={label}><Icon size={20}/><span>{label}</span>{label==='AI Insights'&&<b className="ai-nav-dot"/>}</NavLink>)}</nav>
  <div className="sidebar-bottom"><div className="local-status"><i/> Local workspace</div><div className="profile"><span className="avatar">{initials}</span><div><strong>{account.name}</strong><small>Paper trading account</small></div></div><button className="logout-button" onClick={logout}><LogOut size={15}/> Sign out</button><button className="collapse-button" onClick={()=>setCollapsed(!collapsed)} aria-label="Toggle sidebar"><ChevronLeft size={16}/><span>Collapse sidebar</span></button></div>
 </aside><div className="main-shell"><header className="topbar"><button className="mobile-menu icon-button" aria-label="Toggle menu" onClick={()=>setCollapsed(!collapsed)}><Menu/></button><span className="top-title">{links.find(l=>l[0]===location.pathname)?.[1]||'Stock intelligence'}</span><StockSearch/><div className="market-status"><i/> DAILY SNAPSHOTS</div><div className="notification-wrap"><button className="icon-button" aria-label="Notifications" onClick={()=>setNotifications(!notifications)}><Bell size={19}/><i/></button>{notifications&&<div className="notification-popover"><h3>Workspace notifications</h3><p>Quotes refresh in the background. Synthetic data is labelled DEMO DATA.</p><p>No brokerage account is connected.</p></div>}</div><NavLink to="/settings" className="avatar">{initials}</NavLink></header>
 <main><Routes><Route path="/" element={<Dashboard revision={revision} onAdd={setModal} onRemove={setClosing}/>}/><Route path="/portfolio" element={<Dashboard portfolio revision={revision} onAdd={setModal} onRemove={setClosing}/>}/><Route path="/markets" element={<MarketsPage/>}/><Route path="/watchlist" element={<Watchlist revision={revision} onAdd={setModal} notify={notify} onChange={refresh}/>}/><Route path="/transactions" element={<Transactions revision={revision}/>}/><Route path="/stocks/:symbol" element={<StockDetail onAdd={setModal} notify={notify}/>}/><Route path="/insights" element={<Insights revision={revision} notify={notify}/>}/><Route path="/settings" element={<Settings account={account}/>}/><Route path="*" element={<div className="empty"><h1>Page not found</h1><NavLink to="/">Back to overview</NavLink></div>}/></Routes><footer><span><Waves size={14}/> AquaVest AI</span><p>{disclaimer}</p><span>LOCAL · EDUCATIONAL PROJECT</span></footer></main></div>
 {modal!==null&&<TransactionModal symbol={modal} onClose={close} onSaved={()=>{close();refresh();notify('Simulated transaction recorded')}}/>}
 {closing&&<div className="modal-backdrop"><div className="modal glass" role="dialog" aria-modal="true" aria-labelledby="close-title"><h2 id="close-title">Close {closing} position?</h2><p>This records a simulated SELL of all shares at the latest displayed market snapshot. Demo data may be used. The transaction history is retained.</p><div className="button-group"><button disabled={busy} onClick={()=>setClosing(null)}>Cancel</button><button className="primary" disabled={busy} onClick={async()=>{setBusy(true);try{await api.delete('/portfolio/'+closing);setClosing(null);refresh();notify('Position closed; sale recorded')}catch(e){notify(errorMessage(e))}finally{setBusy(false)}}}>{busy?'Closing…':'Close position'}</button></div></div></div>}
 {toast&&<div role="status" className="toast"><span>{toast}</span><button aria-label="Dismiss notification" onClick={()=>setToast('')}><X size={16}/></button></div>}</div>
}
