## Flow: remote customer 
1. Opens Home -> Join -> picks Haircut + 'Any barber' -> gets S-14, 6th 
2. Watches My Status from home; at 2nd in line gets 'Start coming' 
3. Receptionist taps Call next on Amit's card -> S-14 is 'Called' 
4. Customer's phone: 'It's your turn! Go to Amit'; TV flashes S-14 
5. Amit taps Start, then Done -> S-14 leaves the queue 
  
## Flow: walk-in 
Receptionist taps + Add walk-in -> name, phone, services -> joins the 
same queue at the end (first come, first served). 
  
## Rules 
- Statuses: Waiting -> Called -> In chair -> Done. Never backwards. 
  Waiting -> Cancelled.  Called -> No-show. 
- First come, first served. 
- Call next for barber X picks the earliest customer who chose X or 'Any'. 
- A customer who chose Ravi is never given to another barber. 
- A barber has only one customer in the chair at a time. 
- Waiting time ≈ total minutes of services ahead ÷ barbers working. 
- One active spot per phone number. 
- Called but not here in 10 min -> receptionist can mark No-show; 
  if they arrive later, they're added again at the END. 
- Online joining closes 30 min before closing; walk-ins still allowed. 
- Barber on break -> customers who chose them see 'Ravi is on break'. 
  
## Test checklist 
[ ] Join with 2 services -> correct total time and price shown 
[ ] Same phone joins twice -> shown existing spot, no duplicate 
[ ] Call next for Amit skips a customer who chose Ravi