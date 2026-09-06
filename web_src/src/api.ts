declare global { interface Window { requestSettingsClose?:()=>void; pywebview?: { api: { bootstrap():Promise<{token?:string}>; close():Promise<void> } } } }
let token='';
export async function bootstrap(){
  if(!window.pywebview){
    await new Promise<void>((resolve,reject)=>{
      const timer=setTimeout(()=>{window.removeEventListener('pywebviewready',ready);reject(new Error('设置窗口连接失败，请关闭后从桌宠右键重新打开。'));},12000);
      function ready(){clearTimeout(timer);window.removeEventListener('pywebviewready',ready);resolve();}
      window.addEventListener('pywebviewready',ready);
    });
  }
  token=(await window.pywebview!.api.bootstrap()).token || '';
  if(!token)throw new Error('设置窗口会话无效，请重新打开。');
}
export async function api<T=any>(path:string,body?:unknown,method?:string):Promise<T>{
  const response=await fetch(path,{method:method || (body===undefined?'GET':'POST'),headers:{Authorization:`Bearer ${token}`,'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body),signal:AbortSignal.timeout(50000)});
  const data=await response.json();
  if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:'请求失败，请检查配置。');
  return data as T;
}
