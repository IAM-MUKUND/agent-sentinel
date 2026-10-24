import { useState, useRef, useEffect } from 'react'
import { Shield, Send, Paperclip, Bot, User, LogOut } from 'lucide-react'
import InvoiceTemplate from './InvoiceTemplate';

export default function UserChat({ username, onLogout }) {
  const [messages, setMessages] = useState([
    {
      id: 1,
      role: 'ai',
      content: "Hello! I am Agent Sentinel's Customer Support Assistant. How can I help you today? You can ask me about refunds, replacements, or order tracking."
    }
  ]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const [orders, setOrders] = useState([]);
  const ticketStatusesRef = useRef({});
  
  const messagesEndRef = useRef(null);
  const fileInputRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isTyping]);

  // Fetch orders
  useEffect(() => {
    const fetchOrders = async () => {
      try {
        const response = await fetch(`http://localhost:8000/api/user/orders?username=${username}`);
        if (response.ok) {
          const data = await response.json();
          setOrders(data);
        }
      } catch (err) {
        console.error("Error fetching orders", err);
      }
    };
    if (username) {
      fetchOrders();
    }
  }, [username]);

  // Poll for ticket status updates
  useEffect(() => {
    const fetchTickets = async () => {
      try {
        const response = await fetch(`http://localhost:8000/api/user/tickets?username=${username}`);
        if (response.ok) {
          const tickets = await response.json();
          let newMessages = [];
          
          tickets.forEach(ticket => {
            const oldStatus = ticketStatusesRef.current[ticket.ticket_id];
            
            if (oldStatus !== ticket.status) {
              // Immediately update to prevent race conditions on next poll
              ticketStatusesRef.current[ticket.ticket_id] = ticket.status;
              
              // If it was pending, and now it is not, notify the user!
              if (oldStatus && oldStatus === 'Pending' && ticket.status !== 'Pending') {
                let notificationMsg = `[SYSTEM NOTIFICATION] Your ticket ${ticket.ticket_id} has been ${ticket.status.toUpperCase()} by the Administrator.`;
                const statusLower = ticket.status.toLowerCase();
                
                if (statusLower === 'approved') {
                  switch(ticket.ticket_type) {
                    case 'Technical Support':
                      notificationMsg = `[SYSTEM NOTIFICATION] Your request for technical support (${ticket.ticket_id}) is approved. Our support staff will contact you shortly.`;
                      break;
                    case 'Refund':
                      notificationMsg = `[SYSTEM NOTIFICATION] Your refund request (${ticket.ticket_id}) has been approved. The amount will be credited to your original payment method in 3-5 business days.`;
                      break;
                    case 'Replacement':
                      notificationMsg = `[SYSTEM NOTIFICATION] Your replacement request (${ticket.ticket_id}) has been approved. A new item will be shipped to you shortly.`;
                      break;
                  }
                } else if (statusLower === 'rejected') {
                  switch(ticket.ticket_type) {
                    case 'Technical Support':
                      notificationMsg = `[SYSTEM NOTIFICATION] Your request for technical support (${ticket.ticket_id}) could not be approved at this time.`;
                      break;
                    case 'Refund':
                      notificationMsg = `[SYSTEM NOTIFICATION] Your refund request (${ticket.ticket_id}) was declined. Please contact support for more details.`;
                      break;
                    case 'Replacement':
                      notificationMsg = `[SYSTEM NOTIFICATION] Your replacement request (${ticket.ticket_id}) was declined. Please contact support for more details.`;
                      break;
                  }
                }

                newMessages.push({
                  id: Date.now() + Math.random(),
                  role: 'system',
                  content: notificationMsg
                });
              }
            }
          });
          
          if (newMessages.length > 0) {
            setMessages(prev => [...prev, ...newMessages]);
          }
        }
      } catch (err) {
        console.error("Error fetching tickets", err);
      }
    };
    
    if (username) {
      fetchTickets(); // initial fetch
      const interval = setInterval(fetchTickets, 5000); // poll every 5s
      return () => clearInterval(interval);
    }
  }, [username]);

  const sendMessage = async (messageText, imageUrl = null, base64Image = null) => {
    const userMsg = { id: Date.now(), role: 'user', content: messageText, imageUrl };
    setMessages(prev => [...prev, userMsg]);
    setIsTyping(true);

    try {
      const response = await fetch('http://localhost:8000/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
          username, 
          message: messageText,
          session_id: sessionId,
          image_data: base64Image
        }),
      });
      
      const data = await response.json();
      
      if (response.ok) {
        if (!sessionId) setSessionId(data.session_id);
        
        let replyContent = data.reply;
        let systemContent = null;
        let invoiceData = null;
        
        if (replyContent.includes('[SYSTEM]')) {
          const parts = replyContent.split('[SYSTEM]');
          replyContent = parts[0].trim();
          systemContent = '[SYSTEM] ' + parts[1].trim();
        }

        const invoiceMatch = replyContent.match(/<invoice>([\s\S]*?)<\/invoice>/i);
        if (invoiceMatch) {
            let jsonString = invoiceMatch[1];
            // Remove markdown code block syntax if present
            jsonString = jsonString.replace(/```json/ig, '').replace(/```/ig, '').trim();
            
            // Find bounds of JSON object to ignore any stray text
            const jsonStart = jsonString.indexOf('{');
            const jsonEnd = jsonString.lastIndexOf('}');
            
            if (jsonStart !== -1 && jsonEnd !== -1) {
                jsonString = jsonString.substring(jsonStart, jsonEnd + 1);
                try {
                    invoiceData = JSON.parse(jsonString);
                    // Remove the entire <invoice> block from the visible text
                    replyContent = replyContent.replace(invoiceMatch[0], '').trim();
                } catch (e) {
                    console.error("Failed to parse invoice JSON:", jsonString, e);
                    replyContent = replyContent.replace(invoiceMatch[0], '[Generated Invoice data was malformed]').trim();
                }
            } else {
                replyContent = replyContent.replace(invoiceMatch[0], '').trim();
            }
        }

        setMessages(prev => [...prev, { id: Date.now(), role: 'ai', content: replyContent, invoiceData }]);
        
        if (systemContent) {
           setTimeout(() => {
             setMessages(prev => [...prev, { id: Date.now()+1, role: 'system', content: systemContent }]);
           }, 500);
        }

      } else {
        setMessages(prev => [...prev, { id: Date.now(), role: 'ai', content: "Sorry, I'm having trouble connecting to my brain right now." }]);
      }
    } catch (err) {
      setMessages(prev => [...prev, { id: Date.now(), role: 'ai', content: "Connection error." }]);
    } finally {
      setIsTyping(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!input.trim()) return;
    const text = input;
    setInput('');
    await sendMessage(text);
  };

  const handleFileUpload = (e) => {
    const file = e.target.files[0];
    if (file) {
      const reader = new FileReader();
      reader.onloadend = () => {
        const base64String = reader.result;
        // Create a local blob URL so we can render the actual image the user chose!
        const fileUrl = URL.createObjectURL(file);
        sendMessage(`I have uploaded a picture: ${file.name}`, fileUrl, base64String);
      };
      reader.readAsDataURL(file);
      e.target.value = null; // reset
    }
  };

  return (
    <div className="app-container">
      <div className="sidebar glass-panel">
        <div className="sidebar-header">
          <Shield className="logo-icon" size={28} />
          <h1>Agent Sentinel</h1>
        </div>
        
        <div className="status-card">
          <h3>System Status</h3>
          <div className="status-indicator">
            <div className="dot"></div>
            <span>WAF Middleware Active</span>
          </div>
          <div className="status-indicator">
            <div className="dot" style={{backgroundColor: '#4F46E5', boxShadow: '0 0 10px #4F46E5'}}></div>
            <span>All Agents Online</span>
          </div>
        </div>

        <div className="status-card" style={{marginTop: '1rem', flex: 1, overflowY: 'auto', maxHeight: '300px'}}>
          <h3>Your Recent Orders</h3>
          {orders.length === 0 ? (
            <p style={{fontSize: '0.85rem', color: 'var(--text-muted)'}}>No orders found.</p>
          ) : (
            <ul style={{listStyle: 'none', padding: 0, margin: '0.5rem 0 0 0', display: 'flex', flexDirection: 'column', gap: '0.5rem'}}>
              {orders.map(order => (
                <li key={order.order_id} style={{fontSize: '0.8rem', padding: '0.5rem', backgroundColor: 'rgba(255,255,255,0.05)', borderRadius: '4px', border: '1px solid rgba(255,255,255,0.1)'}}>
                  <div style={{fontWeight: 'bold', color: 'var(--primary)'}}>{order.order_id}</div>
                  <div style={{whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', margin: '2px 0'}} title={order.product_name}>{order.product_name}</div>
                  <div style={{display: 'flex', justifyContent: 'space-between', color: 'var(--text-muted)'}}>
                    <span>{order.status}</span>
                    <span>{order.date}</span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="status-card" style={{marginTop: 'auto'}}>
          <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
            <h3 style={{fontSize: '0.875rem', color: 'var(--text-muted)'}}>Active Session</h3>
            <button onClick={onLogout} style={{background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer'}}>
              <LogOut size={16} />
            </button>
          </div>
          <p style={{fontSize: '0.85rem', marginTop: '0.5rem'}}>User: {username}</p>
        </div>
      </div>

      <div className="chat-container glass-panel">
        <div className="chat-header">
          <div className="chat-header-info">
            <h2>Support Assistant</h2>
            <p>Powered by Llama-3.3-70B</p>
          </div>
          <Bot size={24} color="var(--primary)" />
        </div>

        <div className="messages-area">
          {messages.map((msg) => (
            <div key={msg.id} className={`message-wrapper ${msg.role}`}>
              {msg.role !== 'system' && (
                <div className={`avatar ${msg.role}`}>
                  {msg.role === 'ai' ? <Bot size={20} color="white" /> : <User size={20} color="white" />}
                </div>
              )}
              
              <div className="message-bubble">
                {msg.role === 'system' && <Shield size={16} style={{display: 'inline', marginRight: '8px', verticalAlign: 'text-bottom'}} />}
                {msg.content}
                
                {msg.role === 'user' && msg.imageUrl && (
                  <div className="image-preview">
                    <img src={msg.imageUrl} alt="User Uploaded" />
                  </div>
                )}
                
                {msg.role === 'ai' && msg.invoiceData && (
                  <InvoiceTemplate invoiceData={msg.invoiceData} />
                )}
              </div>
            </div>
          ))}
          
          {isTyping && (
            <div className="message-wrapper ai">
              <div className="avatar ai">
                <Bot size={20} color="white" />
              </div>
              <div className="message-bubble" style={{padding: '1rem 1.5rem'}}>
                <div className="typing-indicator">
                  <div className="typing-dot"></div>
                  <div className="typing-dot"></div>
                  <div className="typing-dot"></div>
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <div className="input-area">
          <form className="input-form" onSubmit={handleSubmit}>
            <input 
              type="file" 
              ref={fileInputRef}
              onChange={handleFileUpload}
              style={{display: 'none'}}
              accept="image/*"
            />
            <button 
              type="button" 
              className="action-btn"
              onClick={() => fileInputRef.current.click()}
            >
              <Paperclip size={20} />
            </button>
            <input 
              type="text" 
              className="chat-input"
              placeholder="Type your message here..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
            />
            <button type="submit" className="action-btn send-btn" disabled={!input.trim()}>
              <Send size={20} />
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}
