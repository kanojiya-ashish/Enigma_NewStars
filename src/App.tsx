import { useEffect, useMemo, useState } from 'react'
import { useAuth } from './auth/AuthContext'
import { AppShell } from './components/AppShell'
import { ErrorBoundary } from './components/ErrorBoundary'
import { LoginPage } from './pages/LoginPage'
import { DashboardPage } from './pages/DashboardPage'
import { MaterialsPage, AddMaterialPage } from './pages/MaterialsPage'
import { AssessmentPage } from './pages/AssessmentPage'
import { MatchingPage } from './pages/MatchingPage'
import { NeedsPage } from './pages/NeedsPage'
import { RequestsPage } from './pages/RequestsPage'
import { RoutePage } from './pages/RoutePage'
import { TransfersPage } from './pages/TransfersPage'
import { TrackingPage } from './pages/TrackingPage'
import { DriversPage } from './pages/DriversPage'
import { OutcomePage, OutcomeReviewPage } from './pages/OutcomePage'
import { ImpactPage } from './pages/ImpactPage'
import { OrganizationsPage } from './pages/OrganizationsPage'
import type { Match, Page } from './types'
import './styles.css'

interface NavState { page: Page; materialId?: number; transferId?: number; match?: Match }

const allowed: Record<string, Page[]> = {
  ORGANIZATION: ['dashboard','materials','add-material','assessment','matching','requests','route','transfers','tracking','impact'],
  RECEIVER: ['dashboard','needs','materials','requests','transfers','tracking','outcome','impact'],
  RECYCLER: ['dashboard','materials','requests','transfers','tracking','outcome','impact'],
  LOGISTICS: ['dashboard','transfers','drivers','tracking','impact'],
  DRIVER: ['dashboard','transfers','tracking'],
  ADMIN: ['dashboard','organizations','transfers','tracking','outcome-review','impact'],
}

export default function App() {
  const { session } = useAuth()
  const [nav,setNav]=useState<NavState>({page:'dashboard'})
  useEffect(()=>{setNav({page:'dashboard'})},[session?.user.id])
  const isAllowed=useMemo(()=>session ? allowed[session.user.role]?.includes(nav.page) ?? false : false,[session,nav.page])
  if(!session) return <ErrorBoundary><LoginPage/></ErrorBoundary>
  const navigate=(page:Page, payload?:{materialId?:number; transferId?:number; match?:Match})=>setNav({page,...payload})
  if(!isAllowed) return <AppShell role={session.user.role} page="dashboard" onNavigate={(page,transferId)=>navigate(page,{transferId})}><div className="redirect-screen"><div><h2>Opening workspace…</h2><p>The selected workflow is not available for this role.</p></div></div></AppShell>

  const content = (() => {
    switch(nav.page){
      case 'dashboard': return <DashboardPage role={session.user.role} onNavigate={p=>navigate(p)}/>
      case 'materials': return <MaterialsPage role={session.user.role} onOpenAssessment={id=>navigate('assessment',{materialId:id})} onOpenMatching={id=>navigate('matching',{materialId:id})}/>
      case 'add-material': return <AddMaterialPage onDone={id=>navigate('assessment',{materialId:id})} onCancel={()=>navigate('materials')}/>
      case 'assessment': return <AssessmentPage materialId={nav.materialId} onNext={id=>navigate('matching',{materialId:id})}/>
      case 'matching': return <MatchingPage materialId={nav.materialId} onTransport={match=>navigate('route',{match})}/>
      case 'needs': return <NeedsPage/>
      case 'requests': return <RequestsPage role={session.user.role} onArrange={match=>navigate('route',{match})} onTrack={id=>navigate('tracking',{transferId:id})}/>
      case 'route': return nav.match ? <RoutePage match={nav.match} onCreated={id=>navigate('tracking',{transferId:id})} onBack={()=>navigate('requests')}/> : <div className="redirect-screen"><h2>No request selected</h2></div>
      case 'transfers': return <TransfersPage role={session.user.role} onTrack={id=>navigate('tracking',{transferId:id})} onOutcome={id=>navigate('outcome',{transferId:id})}/>
      case 'tracking': return <TrackingPage role={session.user.role} transferId={nav.transferId} onOpenOutcome={id=>navigate('outcome',{transferId:id})} onOpenTransfers={()=>navigate('transfers')}/>
      case 'drivers': return <DriversPage/>
      case 'outcome': return <OutcomePage role={session.user.role} transferId={nav.transferId} onDone={()=>navigate('transfers')}/>
      case 'outcome-review': return <OutcomeReviewPage onOpenTracking={id=>navigate('tracking',{transferId:id})}/>
      case 'impact': return <ImpactPage/>
      case 'organizations': return <OrganizationsPage/>
      default: return <DashboardPage role={session.user.role} onNavigate={p=>navigate(p)}/>
    }
  })()

  return <ErrorBoundary><AppShell role={session.user.role} page={nav.page} onNavigate={(page,transferId)=>navigate(page,{transferId})}>{content}</AppShell></ErrorBoundary>
}
