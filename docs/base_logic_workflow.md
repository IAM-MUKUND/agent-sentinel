
    Customer

    │
                    ▼

    User Help Desk (React UI)

    │
                    ▼

    Conversation / Intent Agent
     (LLM Chatbot + Intent Detection)

    │
                    ▼

    Intent Router Agent

    ┌────────┬────────┬────────┬────────┐
      ▼        ▼        ▼        ▼
  Refund   Replace   Shipping  Complaint
   Agent     Agent      Agent      Agent
      │        │          │          │
      ├────────┼──────────┼──────────┤
               ▼

    Agent Sentinel
     (Policy Enforcement)

    │
      Allow / Reject / HITL
               │
      ┌────────┴─────────┐
      ▼                  ▼
 Execute Tool      Admin Dashboard
      │                  ▲
      └──────────┬───────┘
                 ▼
          Notification Agent
                 ▼
          Customer Dashboard
