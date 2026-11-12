/** Authored replay data for S-RASTER-1. These values are never scientific computation. */
export const marsMobility = {
 states:['VALIDATING','CHARACTERIZING','DISCOVERING','QUALIFYING','CRITIQUING','AWAITING_REVIEW'],
 attempts:[
 {candidate:'Practice grid-r0c1',strategy:'WAYPOINT_RETURN',outcome:'FAIL',failureCategory:'ROUTE',searchStatus:'FOUND',distance:120,energy:26,exposure:0,reason:'EXPOSURE_SHORTFALL',next:'NEW_ROUTE'},
 {candidate:'Practice grid-r0c1',strategy:'EXPOSURE_COVERAGE',outcome:'FAIL',failureCategory:'ANALOG',searchStatus:'EXHAUSTIVE_INFEASIBLE',distance:null,energy:null,exposure:0,reason:'Unreachable slope band enclosed by water moat',next:'NEW_CANDIDATE'},
 {candidate:'Practice grid-r0c0',strategy:'EXPOSURE_COVERAGE',outcome:'PASS',failureCategory:null,searchStatus:'FOUND',distance:230,energy:30,exposure:150,reason:'ROUTE_VERIFIED',next:null},
 ],
};
