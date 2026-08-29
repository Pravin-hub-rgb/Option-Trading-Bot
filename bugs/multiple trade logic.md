From backend/upstox/data_streamer.py:263-274:
- pnl > 0 (WIN) → can_trade = False → no second trade on that side
- pnl <= 0 (LOSS or BREAKEVEN) → allow slot 2 → second trade allowed


umm i think we should be smart here cuse 0.1 will still considered as win but that is breakeven 
as in trade we mostly exit on neg but sometime we can exit at 0.1 too nah .. it should be like > 1 or somthing ... i think for loss too like -0.1 will be considered as loss but it is breakeven ... in a sense

cuse i can't exit at exact 0.00 to call it breakeven cuse these are real trades .. can't exit at exact 0.00 nah it can be like +0.01 or -0.01 both are still breakeven nah..
may be it should be 
for win pnl > 1
and loss pnl < 1 and 
for breakeven give it a range??? -1 to +1???
i don't know man ..
but please be smart here