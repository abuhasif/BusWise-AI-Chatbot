export type LocationFix={latitude:number;longitude:number;accuracy:number};
export function locateDevice(geo:Geolocation,signal:AbortSignal,onRetry:()=>void):Promise<LocationFix>{
 return new Promise((resolve,reject)=>{
  let done=false;
  const finish=(error?:Error,fix?:LocationFix)=>{if(done)return;done=true;signal.removeEventListener('abort',cancel);if(error)reject(error);else resolve(fix!);};
  const cancel=()=>finish(new Error('Location request cancelled.'));
  if(signal.aborted){cancel();return;}signal.addEventListener('abort',cancel,{once:true});
  const request=(precise:boolean)=>geo.getCurrentPosition(p=>{
   if(done)return;
   const {latitude,longitude,accuracy}=p.coords;
   if(!Number.isFinite(latitude)||!Number.isFinite(longitude)||!Number.isFinite(accuracy)||latitude<1.14||latitude>1.5||longitude<103.5||longitude>104.51){finish(new Error('Your device returned a location outside Singapore. Pick your start on the map instead.'));return;}
   finish(undefined,{latitude,longitude,accuracy});
  },error=>{
   if(done)return;
   if(error.code!==1&&!precise){onRetry();request(true);return;}
   finish(new Error(error.code===1?'Location permission is blocked. Allow location for this site and in Windows location settings, then retry. You can also pick a map point.':'Your device could not find its location. Try Chrome or Edge with location enabled, or pick your start on the map.'));
  },{enableHighAccuracy:precise,timeout:precise?20000:10000,maximumAge:precise?0:60000});
  request(false);
 });
}
