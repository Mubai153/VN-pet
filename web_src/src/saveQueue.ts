/** Serialize saves. A newer draft always follows the in-flight save. */
export function createSaveQueue<T>(save:(value:T)=>Promise<void>,error:(e:unknown)=>void,delay=500){
  let pending:T|undefined, timer:ReturnType<typeof setTimeout>|undefined, running:Promise<void>|undefined;
  let lastError:unknown;
  async function drain(){
    if(running)return running;
    running=(async()=>{
      while(pending!==undefined){
        const next=pending;pending=undefined;
        try{await save(next);lastError=undefined;}catch(e){lastError=e;error(e);}
      }
    })();
    try{await running;}finally{running=undefined;}
  }
  return {
    schedule(value:T){pending=structuredClone(value);clearTimeout(timer);timer=setTimeout(()=>{void drain();},delay);},
    async flush(){clearTimeout(timer);await drain();const error=lastError;lastError=undefined;if(error)throw error;},
    cancel(){clearTimeout(timer);pending=undefined;}
  };
}
