import { useState, useEffect } from 'react';
import { Shield, AlertTriangle, CheckCircle, XCircle, Clock, LogOut, Activity, Users, MessageSquare } from 'lucide-react';

export default function AdminDashboard({ username, onLogout }) {
  const [activeTab, setActiveTab] = useState('tickets');
  const [tickets, setTickets] = useState([]);
  const [wafLogs, setWafLogs] = useState([]);
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expandedSession, setExpandedSession] = useState(null);

  const fetchData = async () => {
    try {
      if (activeTab === 'tickets') {
        const res = await fetch('http://localhost:8000/api/admin/tickets');
        if (res.ok) setTickets(await res.json());
      } else if (activeTab === 'waf') {
        const res = await fetch('http://localhost:8000/api/admin/waf-logs');
        if (res.ok) setWafLogs(await res.json());
      } else if (activeTab === 'sessions') {
        const res = await fetch('http://localhost:8000/api/admin/sessions');
        if (res.ok) setSessions(await res.json());
      }
    } catch (err) {
      console.error("Error fetching data", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    setLoading(true);
    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, [activeTab]);

  const handleAction = async (id, action) => {
    setTickets(tickets.map(t => t.id === id ? { ...t, status: action } : t));
    try {
      await fetch(`http://localhost:8000/api/admin/tickets/${id}/resolve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, admin_username: username }),
      });
    } catch (err) {
      console.error("Failed to resolve ticket", err);
    }
  };

  const getDecisionColor = (decision) => {
    if (decision === 'ALLOW') return '#10b981';
    if (decision === 'DENY') return '#ef4444';
    if (decision === 'HITL') return '#f59e0b';
    return 'var(--text)';
  };

  return (
    <div className="app-container">
      <div className="sidebar glass-panel">
        <div className="sidebar-header">
          <Shield className="logo-icon" size={28} style={{ color: 'var(--secondary)' }} />
          <h1>Admin Desk</h1>
        </div>
        
        <div style={{ marginTop: '2rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          <button 
            onClick={() => setActiveTab('tickets')}
            style={{ padding: '0.75rem', background: activeTab === 'tickets' ? 'rgba(255,255,255,0.1)' : 'transparent', border: 'none', color: 'var(--text)', textAlign: 'left', borderRadius: '8px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '10px' }}
          >
            <AlertTriangle size={18} /> Pending Tickets
          </button>
          <button 
            onClick={() => setActiveTab('waf')}
            style={{ padding: '0.75rem', background: activeTab === 'waf' ? 'rgba(255,255,255,0.1)' : 'transparent', border: 'none', color: 'var(--text)', textAlign: 'left', borderRadius: '8px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '10px' }}
          >
            <Activity size={18} /> WAF Security Logs
          </button>
          <button 
            onClick={() => setActiveTab('sessions')}
            style={{ padding: '0.75rem', background: activeTab === 'sessions' ? 'rgba(255,255,255,0.1)' : 'transparent', border: 'none', color: 'var(--text)', textAlign: 'left', borderRadius: '8px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '10px' }}
          >
            <Users size={18} /> User Sessions
          </button>
        </div>

        <div className="status-card" style={{marginTop: 'auto'}}>
          <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
            <h3 style={{fontSize: '0.875rem', color: 'var(--text-muted)'}}>Active Session</h3>
            <button onClick={onLogout} style={{background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer'}}>
              <LogOut size={16} />
            </button>
          </div>
          <p style={{fontSize: '0.85rem', marginTop: '0.5rem'}}>Role: Administrator</p>
          <p style={{fontSize: '0.85rem'}}>User: {username}</p>
        </div>
      </div>

      <div className="admin-content glass-panel" style={{ overflowY: 'auto' }}>
        
        {activeTab === 'tickets' && (
          <>
            <div className="admin-header">
              <h2>Pending Human-in-the-Loop Approvals</h2>
              <p>Review agent escalations before execution. Data loaded from MongoDB Atlas.</p>
            </div>
            {loading ? (
               <div style={{textAlign: 'center', padding: '2rem'}}>Loading tickets...</div>
            ) : tickets.length === 0 ? (
               <div style={{textAlign: 'center', padding: '2rem'}}>No tickets found.</div>
            ) : (
              <div className="tickets-list">
                {tickets.map(ticket => (
                  <div key={ticket.id} className={`ticket-card ${ticket.status.toLowerCase()}`}>
                    <div className="ticket-header">
                      <div className="ticket-title">
                        <AlertTriangle size={18} color={ticket.riskScore === 'High' ? '#ef4444' : 'var(--secondary)'} />
                        <h3>{ticket.id} - {ticket.type}</h3>
                      </div>
                      <span className="ticket-time"><Clock size={14}/> {ticket.time}</span>
                    </div>
                    
                    <div className="ticket-body">
                      <p><strong>Customer:</strong> {ticket.customer}</p>
                      {ticket.order_id && <p><strong>Order ID:</strong> {ticket.order_id}</p>}
                      
                      {ticket.order_details && (
                        <div className="order-details-box" style={{ background: 'rgba(255,255,255,0.05)', padding: '0.75rem', borderRadius: '6px', marginTop: '0.5rem', marginBottom: '0.5rem', fontSize: '0.85rem' }}>
                          <p style={{marginBottom: '0.25rem'}}><strong>Product:</strong> {ticket.order_details.product_name}</p>
                          <p style={{marginBottom: '0.25rem'}}><strong>Amount:</strong> ${ticket.order_details.total_amount.toFixed(2)}</p>
                          <p style={{marginBottom: '0.25rem'}}><strong>Purchase Date:</strong> {ticket.order_details.purchase_date}</p>
                          <p style={{marginBottom: 0}}><strong>Order Status:</strong> {ticket.order_details.order_status}</p>
                        </div>
                      )}

                      <p><strong>Reason:</strong> {ticket.reason}</p>
                      <p><strong>Risk Score:</strong> <span style={{color: ticket.riskScore === 'High' ? '#ef4444' : 'var(--secondary)'}}>{ticket.riskScore}</span></p>
                      {ticket.image_data && (
                        <div style={{ marginTop: '0.75rem' }}>
                          <p style={{ marginBottom: '0.25rem' }}><strong>Attachment:</strong></p>
                          <img src={ticket.image_data} alt="Request Attachment" style={{ maxWidth: '100%', maxHeight: '200px', borderRadius: '6px', border: '1px solid var(--border)' }} />
                        </div>
                      )}
                    </div>
                    
                    {ticket.type !== 'Auto-Cancellation' && (
                      <div className="ticket-actions">
                        {ticket.status === 'Pending' ? (
                          <>
                            <button className="approve-btn" onClick={() => handleAction(ticket.id, 'Approved')}>
                              <CheckCircle size={16} /> Approve
                            </button>
                            <button className="deny-btn" onClick={() => handleAction(ticket.id, 'Denied')}>
                              <XCircle size={16} /> Deny
                            </button>
                          </>
                        ) : (
                          <div className={`status-badge ${ticket.status.toLowerCase()}`}>
                            {ticket.status === 'Approved' ? <CheckCircle size={16} /> : <XCircle size={16} />}
                            {ticket.status}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </>
        )}

        {activeTab === 'waf' && (
          <>
            <div className="admin-header">
              <h2>WAF Security Logs</h2>
              <p>Real-time observability of the WAF Middleware decisions.</p>
            </div>
            {loading ? (
               <div style={{textAlign: 'center', padding: '2rem'}}>Loading logs...</div>
            ) : wafLogs.length === 0 ? (
               <div style={{textAlign: 'center', padding: '2rem'}}>No WAF logs found.</div>
            ) : (
              <div style={{ background: 'rgba(255,255,255,0.02)', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.1)', overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.1)', textAlign: 'left' }}>
                      <th style={{ padding: '1rem' }}>Timestamp</th>
                      <th style={{ padding: '1rem' }}>Agent / Tool</th>
                      <th style={{ padding: '1rem' }}>Decision</th>
                      <th style={{ padding: '1rem' }}>Policy Matched</th>
                      <th style={{ padding: '1rem' }}>Reason</th>
                    </tr>
                  </thead>
                  <tbody>
                    {wafLogs.map(log => (
                      <tr key={log._id} style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                        <td style={{ padding: '1rem' }}>{new Date(log.timestamp).toLocaleString()}</td>
                        <td style={{ padding: '1rem' }}>
                          <div style={{ fontWeight: 'bold' }}>{log.agent_id}</div>
                          <div style={{ color: 'var(--text-muted)' }}>{log.tool_name}</div>
                        </td>
                        <td style={{ padding: '1rem', fontWeight: 'bold', color: getDecisionColor(log.decision) }}>
                          {log.decision}
                          <div style={{ fontSize: '0.75rem', fontWeight: 'normal', color: 'var(--text-muted)' }}>{log.evaluation_latency_ms.toFixed(1)}ms</div>
                        </td>
                        <td style={{ padding: '1rem' }}>{log.matched_policy || 'N/A'}</td>
                        <td style={{ padding: '1rem', maxWidth: '300px' }}>{log.decision_reason}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}

        {activeTab === 'sessions' && (
          <>
            <div className="admin-header">
              <h2>All User Sessions</h2>
              <p>End-to-end trace of user interactions and generated tickets.</p>
            </div>
            {loading ? (
               <div style={{textAlign: 'center', padding: '2rem'}}>Loading sessions...</div>
            ) : sessions.length === 0 ? (
               <div style={{textAlign: 'center', padding: '2rem'}}>No sessions found.</div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                {sessions.map(session => (
                  <div key={session._id} style={{ background: 'rgba(255,255,255,0.02)', padding: '1rem', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.1)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', cursor: 'pointer' }} onClick={() => setExpandedSession(expandedSession === session._id ? null : session._id)}>
                      <div>
                        <h3 style={{ fontSize: '1.1rem', marginBottom: '0.25rem' }}>{session.username || 'Anonymous User'}</h3>
                        <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>Session ID: {session.session_id} | Last Updated: {new Date(session.last_updated).toLocaleString()}</div>
                      </div>
                      <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
                         {session.invoked_tickets && session.invoked_tickets.length > 0 && (
                            <span style={{ background: 'rgba(239, 68, 68, 0.2)', color: '#ef4444', padding: '4px 8px', borderRadius: '4px', fontSize: '0.8rem', fontWeight: 'bold' }}>
                              {session.invoked_tickets.length} Ticket(s)
                            </span>
                         )}
                         <button style={{ background: 'none', border: '1px solid rgba(255,255,255,0.2)', color: 'var(--text)', padding: '0.5rem 1rem', borderRadius: '4px', cursor: 'pointer' }}>
                           {expandedSession === session._id ? 'Collapse' : 'View Transcript'}
                         </button>
                      </div>
                    </div>

                    {expandedSession === session._id && (
                      <div style={{ marginTop: '1.5rem', paddingTop: '1.5rem', borderTop: '1px solid rgba(255,255,255,0.1)' }}>
                        <h4 style={{ marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}><MessageSquare size={16} /> Chat Transcript</h4>
                        
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', background: '#0f172a', padding: '1rem', borderRadius: '8px', maxHeight: '400px', overflowY: 'auto' }}>
                          {session.history && session.history.map((msg, i) => (
                            <div key={i} style={{ 
                              alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start',
                              background: msg.role === 'user' ? 'var(--primary)' : 'rgba(255,255,255,0.05)',
                              padding: '0.75rem 1rem',
                              borderRadius: '8px',
                              maxWidth: '80%',
                              border: msg.role === 'tool' ? '1px dashed rgba(255,255,255,0.2)' : 'none'
                            }}>
                              <div style={{ fontSize: '0.7rem', textTransform: 'uppercase', color: 'rgba(255,255,255,0.5)', marginBottom: '0.25rem' }}>{msg.role} {msg.name ? `(${msg.name})` : ''}</div>
                              {msg.content ? (
                                <div style={{ whiteSpace: 'pre-wrap', fontSize: '0.9rem' }}>{msg.content}</div>
                              ) : msg.tool_calls ? (
                                <div style={{ fontSize: '0.8rem', fontFamily: 'monospace', color: 'var(--secondary)' }}>
                                  [Invoking Tool: {msg.tool_calls[0].function.name}]
                                </div>
                              ) : null}
                            </div>
                          ))}
                        </div>

                        {session.admin_actions && session.admin_actions.length > 0 && (
                          <div style={{ marginTop: '1.5rem' }}>
                            <h4 style={{ marginBottom: '0.75rem' }}>Admin Interventions</h4>
                            {session.admin_actions.map((act, i) => (
                              <div key={i} style={{ fontSize: '0.85rem', padding: '0.5rem', background: 'rgba(255,255,255,0.05)', borderRadius: '4px', marginBottom: '0.5rem' }}>
                                <strong>{act.admin_username}</strong> {act.action.toLowerCase()} ticket {act.ticket_id} on {new Date(act.timestamp).toLocaleString()}
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </>
        )}

      </div>
    </div>
  );
}
