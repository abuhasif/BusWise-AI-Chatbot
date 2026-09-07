import type {MapResult} from './journey-map';
export function explainJourney(question:string,result:MapResult|null,selected=0):string|null{
 const text=question.toLowerCase();
 if(!/where.*(change|transfer)|explain.*(route|option)|how long.*(that|this|second|first|third|option)|\b(first|second|third) (route|option)\b/.test(text))return null;
 if(!result)return 'Search for a journey first, then ask about one of its options.';
 const ordinal=/\b(first|second|third)\b/.exec(text);
 const index=ordinal?['first','second','third'].indexOf(ordinal[1]):selected;
 const route=result.routes[index];
 if(!route)return `There are ${result.routes.length} options in the last search. Please choose one of those.`;
 const steps=route.legs.map(l=>`${l.mode==='BUS'?'Take bus '+l.service:'Walk'} from ${l.from} to ${l.to}.`);
 return `Option ${index+1}: ${route.label}.${route.minutes!==undefined?` Estimated journey time: ${route.minutes} minutes.`:' Journey time is unavailable in this snapshot.'}\n`+steps.join('\n');
}
