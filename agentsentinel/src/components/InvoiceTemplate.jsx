import React, { useRef } from 'react';
import html2canvas from 'html2canvas';

export default function InvoiceTemplate({ invoiceData }) {
  const invoiceRef = useRef(null);

  const downloadInvoice = async () => {
    if (invoiceRef.current) {
      const canvas = await html2canvas(invoiceRef.current, { scale: 2 });
      const image = canvas.toDataURL("image/png");
      const link = document.createElement("a");
      link.href = image;
      link.download = `Invoice_${invoiceData.invoice_number}.png`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    }
  };

  if (!invoiceData) return null;

  return (
    <div style={{ marginTop: '1rem', marginBottom: '1rem' }}>
      <div 
        ref={invoiceRef}
        style={{
          background: 'white',
          color: '#333',
          padding: '2rem',
          borderRadius: '8px',
          fontFamily: 'sans-serif',
          width: '100%',
          maxWidth: '500px',
          boxShadow: '0 4px 6px rgba(0,0,0,0.1)'
        }}
      >
        <div style={{ borderBottom: '2px solid #eee', paddingBottom: '1rem', marginBottom: '1rem', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <h2 style={{ margin: 0, color: '#4F46E5', fontSize: '1.5rem', fontWeight: 'bold' }}>{invoiceData.company_name}</h2>
            <p style={{ margin: '0.25rem 0 0 0', fontSize: '0.85rem', color: '#666' }}>Invoice #: {invoiceData.invoice_number}</p>
            <p style={{ margin: '0.25rem 0 0 0', fontSize: '0.85rem', color: '#666' }}>Date: {invoiceData.date}</p>
          </div>
          <div>
            <h1 style={{ margin: 0, fontSize: '2rem', color: '#ddd' }}>INVOICE</h1>
          </div>
        </div>

        <div style={{ marginBottom: '2rem' }}>
          <h3 style={{ fontSize: '1rem', borderBottom: '1px solid #eee', paddingBottom: '0.5rem', marginBottom: '0.5rem' }}>Billed To:</h3>
          <p style={{ margin: '0.25rem 0', fontWeight: 'bold' }}>{invoiceData.purchaser.name}</p>
          <p style={{ margin: '0.25rem 0', fontSize: '0.9rem' }}>{invoiceData.purchaser.address}</p>
          <p style={{ margin: '0.25rem 0', fontSize: '0.9rem' }}>Phone: {invoiceData.purchaser.phone}</p>
        </div>

        <table style={{ width: '100%', borderCollapse: 'collapse', marginBottom: '1.5rem' }}>
          <thead>
            <tr style={{ backgroundColor: '#f9fafb', borderBottom: '1px solid #eee' }}>
              <th style={{ padding: '0.75rem', textAlign: 'left', fontSize: '0.9rem' }}>Item</th>
              <th style={{ padding: '0.75rem', textAlign: 'center', fontSize: '0.9rem' }}>Qty</th>
              <th style={{ padding: '0.75rem', textAlign: 'right', fontSize: '0.9rem' }}>Amount</th>
            </tr>
          </thead>
          <tbody>
            <tr style={{ borderBottom: '1px solid #eee' }}>
              <td style={{ padding: '0.75rem', fontSize: '0.9rem' }}>{invoiceData.order_details.product_name}</td>
              <td style={{ padding: '0.75rem', textAlign: 'center', fontSize: '0.9rem' }}>{invoiceData.order_details.quantity}</td>
              <td style={{ padding: '0.75rem', textAlign: 'right', fontSize: '0.9rem' }}>${invoiceData.order_details.total_amount.toFixed(2)}</td>
            </tr>
          </tbody>
        </table>

        <div style={{ display: 'flex', justifyContent: 'flex-end', borderTop: '2px solid #eee', paddingTop: '1rem' }}>
          <div style={{ width: '50%' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem', fontWeight: 'bold', fontSize: '1.1rem' }}>
              <span>Total:</span>
              <span>${invoiceData.order_details.total_amount.toFixed(2)}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.9rem', color: invoiceData.order_details.payment_status === 'paid' ? 'green' : 'orange' }}>
              <span>Status:</span>
              <span style={{ textTransform: 'capitalize' }}>{invoiceData.order_details.payment_status}</span>
            </div>
          </div>
        </div>
      </div>
      
      <button 
        onClick={downloadInvoice}
        style={{
          marginTop: '1rem',
          padding: '0.75rem 1.5rem',
          backgroundColor: '#4F46E5',
          color: 'white',
          border: 'none',
          borderRadius: '4px',
          cursor: 'pointer',
          fontWeight: 'bold',
          display: 'flex',
          alignItems: 'center',
          gap: '0.5rem'
        }}
      >
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
          <polyline points="7 10 12 15 17 10"></polyline>
          <line x1="12" y1="15" x2="12" y2="3"></line>
        </svg>
        Download Invoice
      </button>
    </div>
  );
}
