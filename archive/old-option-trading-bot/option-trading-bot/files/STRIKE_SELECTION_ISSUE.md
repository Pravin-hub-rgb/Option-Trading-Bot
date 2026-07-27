# Strike Selection Issue - Premium Target Problem

## 🎯 THE PROBLEM

**Current Status:** Strike selector is now getting correct previous close, but strike selection still fails.

**Why?** The logic doesn't correctly predict which strikes will open at ₹90-120 premium range.

---

## 📊 WHAT I NEED

### Target Requirements:
- **Opening premium per leg:** ₹90-120 (affordable range)
- **Works on all gap sizes:** Small (±50), Medium (±200), Large (±500), Extreme (±1000+)
- **Works every day:** Including expiry days (0 DTE)

### Current Problem:
```
Example - Today (Feb 3):
Gap: +1228 points (extreme)
Bot tried: 100 points OTM strikes
Result: These would open at ₹300-400 (too expensive!) ❌

What I Need:
Strikes that open at ₹90-120 regardless of gap size ✅
```

---

## 💡 THE SOLUTION NEEDED

**Adaptive OTM Distance Formula:**

The bot needs to calculate how far OTM (Out of The Money) to go based on gap size:

- **Small gap (±50):** Go ~90 points OTM → Opens at ₹90-120
- **Medium gap (±200):** Go ~150 points OTM → Opens at ₹90-120  
- **Large gap (±500):** Go ~350 points OTM → Opens at ₹90-120
- **Extreme gap (±1200):** Go ~800 points OTM → Opens at ₹90-120

### Gap Direction Matters:
- **Gap UP:** CE should be farther OTM (cheaper), PE closer (more expensive)
- **Gap DOWN:** PE should be farther OTM (cheaper), CE closer (more expensive)

---

## 🔍 THE UNKNOWN

**We don't have the exact formula yet!**

We need to find the relationship:
```
OTM Distance = f(gap_size, gap_direction) 
    such that opening_premium ≈ ₹100
```

### Required Data Collection:

For next 5-10 trading days, track:
```
Date: ___
Gap: ___
CE Strike Distance from Spot: ___
PE Strike Distance from Spot: ___
CE Opening Premium (at 9:15): ___
PE Opening Premium (at 9:15): ___
Within target (₹90-120)? YES/NO
```

After collecting this data, we can build the accurate formula.

---

## ⚡ IMMEDIATE OPTIONS

### Option A: Use Estimated Formula (Untested)
Implement best-guess adaptive logic based on general option pricing behavior.

**Risk:** May not be accurate, needs tuning over time.

### Option B: Skip Extreme Gap Days
Add safety check:
```python
if abs(gap) > 500:
    log("Extreme gap - skipping trading today")
    return None
```

**Risk:** Miss trading days, but safer.

### Option C: Collect Data First
Manually observe for 5-10 days:
- What strikes open at ₹90-120?
- Build formula from real data
- Then automate

**Risk:** Lose trading time, but most accurate.

---

## 📋 FILES TO MODIFY

**File:** `upstox/strike_selector.py`

**Method:** `select_strikes()` 

**Change Needed:** Replace current strike selection logic with adaptive OTM distance calculation.

---

## ✅ SUCCESS CRITERIA

Strike selection is successful when:

1. Bot selects strikes at 9:07-9:09 AM
2. Market opens at 9:15 AM
3. Selected CE opens at ₹90-120
4. Selected PE opens at ₹90-120
5. Works on small, medium, large, and extreme gap days

---

## 🎯 DECISION NEEDED

**Which approach to take:**
- [ ] A - Implement estimated formula now (may need tuning)
- [ ] B - Skip extreme gap days (>500 points)
- [ ] C - Collect data manually first (5-10 days)

---

**Current Status:** Awaiting decision on approach  
**Blocker:** No proven formula for OTM distance vs opening premium  
**Next Step:** Choose option A, B, or C
