Visit https://ecotransitdeadline.streamlit.app/

EcoTransit: Green Freight Optimizer + Real-Time Route Climate Safety
Hubs: Ahmedabad, Bengaluru, Chennai, Delhi, Hyderabad, Jaipur, Kolkata, Mumbai, Nagpur

Shipment Parameters:
From hub: Delhi
To hub: Chennai
Shipment weight: 10 tonnes
Priorities: Carbon reduction: 60% | Low cost: 30% | Delivery speed: 10%

==================================================

1. FASTEST-ONLY PLAN (Standard expedited logistics)
==================================================
Route: Delhi -> Nagpur -> Hyderabad -> Chennai



* Delhi -> Nagpur (1050 km) by Air


* Nagpur -> Hyderabad (500 km) by Air


* Hyderabad -> Chennai (630 km) by Air
Time: 21.1 hrs | Cost: Rs 261,600 | CO2: 13,080 kg



# ==================================================
2. YOUR OPTIMIZED ECOTRANSIT PLAN (Unconstrained)



Route: Delhi -> Nagpur -> Hyderabad -> Chennai

* Delhi -> Nagpur (1050 km) by Rail


* Nagpur -> Hyderabad (500 km) by Rail


* Hyderabad -> Chennai (630 km) by Rail
Time: 84.4 hrs | Cost: Rs 26,160 | CO2: 545 kg



Impact vs Fastest:

* CO2 saved: 12,535 kg (96% less)
* Cost saved: Rs 235,440 (90% less)
* Extra time: 63.3 hrs

# ==================================================
3. DELIVERY DEADLINE SWEEP (Constrained Optimization)



* 100 hrs: Feasible | Route: Delhi > Nagpur > Hyderabad > Chennai | Modes: Rail/Rail/Rail | Time: 84.4 hrs | Cost: Rs 26,160 | CO2: 545 kg


* 80 hrs: Feasible | Route: Delhi > Nagpur > Hyderabad > Chennai | Modes: Rail/Road/Rail | Time: 76.8 hrs | Cost: Rs 32,660 | CO2: 870 kg


* 60 hrs: Feasible | Route: Delhi > Nagpur > Hyderabad > Chennai | Modes: Road/Air/Road | Time: 54.7 hrs | Cost: Rs 102,000 | CO2: 4,512 kg


* 20 hrs: Feasible | Route: Delhi > Kolkata > Chennai | Modes: Air/Air | Time: 16.5 hrs | Cost: Rs 380,400 | CO2: 19,020 kg


* 16 hrs: Infeasible (Fastest achievable time: 16.53 hrs)



# ==================================================
4. REAL-TIME CORRIDOR CLIMATE & AI SAFETY



* Live Weather: Real-time temperature, precipitation, and wind speeds fetched along corridor hubs via Open-Meteo API.


* Rule Engine: Monitors wet road slickness/hydroplaning (>5mm rain), extreme corridor heat (>42°C), high airport crosswinds (>40 km/h), and monsoon rail track flooding (>20mm rain).


* AI Advisory: Gemini-powered risk assessment and dispatch recommendations for active transit routes.
