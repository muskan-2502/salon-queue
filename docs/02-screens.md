## Screen 1: Home  (/) 
- Salon name + logo, 'Open · Closes 9 PM' badge 
- Live card: '6 people waiting · about 50 min' · Cancel my spot
- Barber chips with status: Ravi (busy) · Amit (free) · Imran (on break/ Unavailable) · Estimated Waiting time for each barber seperately
- Big deep purple button [ Join Queue ] 
  
## Screen 2: Join Queue  (/join) 
- Name, Phone (10 digits, validated) 
- Service cards (multi-select, max 3): Haircut 30 min ₹150, 
  Beard trim 15 min ₹80, Hair spa 45 min ₹400 … 
- Barber picker: 'Any barber (fastest)' or a barber's photo card 
- Live summary: 'Total 45 min · ₹230 · Expected wait ~35 min' 
- [ Confirm ] -> goes to My Status 
  
## Screen 3: My Status  (/status/:id) 
- Token 'S-14' large, position '4th in line' 
- Small service cards that were selected with service name below them 
- Circular countdown: 'about 35 min'; updates by itself 
- When 2nd in line: banner 'Start coming to the salon' 
- When called: full-screen gold 'It's your turn! Go to Ravi' 
- [ Cancel my spot ] with a confirmation pop-up 
  
## Screen 4: Reception Dashboard  (/reception)   — tablet 
- Left: barber cards (current customer, time left, [Call next]) 
- Right: waiting list in order: token, name, services, 
  preferred barber, waiting time, [No-show] [Cancel] 
- Top: [ + Add walk-in ] opens a quick form 
- Waiting > 60 min highlighted in amber 
  
## Screen 5: Barber View  (/barber/:name)   — phone 
- Current customer: name, services, timer since start 
- Big buttons: [ Start ] -> [ Done ] 
- 'Next for you: S-15 Kunal (Haircut)' 
- Toggle: On break / Available 
  
## Screen 6: Waiting Area TV  (/display) 
- Row per barber: photo, name, 'Now: S-12' 
- 'Up next' list of 5 tokens with estimated times per barber in the same row but a bit to right seperating the barber and its current customer
- Newly-called token flashes gold + chime 
- The list of customers per barber in the row gets updated in real time without any refresh
  
## Screen 7: Owner Settings  (/admin) 
- Services list (name EN/GU, minutes, price, on/off) 
- Barbers on duty today (toggle) 
- Queue switch: Open / Closed for online joining 
- Today's stats: customers served, average wait, no-shows