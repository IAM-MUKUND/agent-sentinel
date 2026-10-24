1. Conversation Agent (Entry Agent)

Role

This is the chatbot that the customer talks to.

Examples:

"My order hasn't arrived."

"I want a refund."

"Cancel my order."

Responsibilities

Understand natural language
Ask follow-up questions
Collect missing information
Extract entities (Order ID, Product, Reason)

Example

Customer:
My headphones are damaged.

Conversation Agent:
I'm sorry to hear that.
Could you please provide your Order ID?


2. Intent Router Agent

After the conversation agent understands the request, it forwards it to the appropriate specialist.

Possible intents:

Refund
Replacement
Cancellation
Shipping
Billing
Complaint
Technical Support
Coupon

This is your fan-out agent.

3. Refund Agent

Responsible for

Verify refund eligibility
Calculate refund amount
Initiate refund request
Forward high-value refunds for approval

Example

Order

↓

Delivered 3 days ago

↓

Refund allowed

↓

Proceed
4. Replacement Agent

Responsible for

Check warranty
Check inventory
Reserve replacement
Create replacement order

Example

Damaged Product

↓

Inventory Available

↓

Replacement Created
5. Order Management Agent

Instead of separate "Shipping" and "Cancellation" agents, combine them.

Responsibilities

Track shipment
Cancel order
Modify delivery address
Update shipping status

This keeps the architecture cleaner.

6. Billing Agent

Responsible for

Invoice generation
Payment verification
Failed payments
Duplicate charges
Tax information
7. Complaint & Technical Support Agent

Merge these into one.

Responsibilities

Product complaints
Technical troubleshooting
Escalation
Ticket creation

If unresolved

↓

Create support ticket

↓

Escalate

8. Notification Agent

Responsible for notifying users.

Instead of Email/SMS:

Update customer dashboard
Update admin dashboard
Push WebSocket notification
Store notification history

Example

Refund Approved

↓

Customer Portal

↓

Notification appears
9. Analytics Agent (Optional but impressive)

This agent doesn't interact with customers.

It periodically computes:

Number of refunds
Average response time
Most common complaints
Fraud attempts
Pending approvals

Useful for an admin dashboard.
