import { describe,it,expect,vi,afterEach } from 'vitest';
import { createSaveQueue } from './saveQueue';
afterEach(()=>vi.useRealTimers());
describe('serialized settings saves',()=>{
 it('coalesces drafts before saving',async()=>{vi.useFakeTimers();const save=vi.fn(async()=>{});const q=createSaveQueue(save,()=>{});q.schedule({n:1});q.schedule({n:2});await q.flush();expect(save.mock.calls).toEqual([[{n:2}]]);});
 it('sends newest draft after an in-flight request',async()=>{let release!:()=>void;const seen:number[]=[];const q=createSaveQueue<number>(async n=>{seen.push(n);if(n===1)await new Promise<void>(r=>release=r);},()=>{});q.schedule(1);const first=q.flush();await Promise.resolve();q.schedule(2);q.schedule(3);release();await first;await q.flush();expect(seen).toEqual([1,3]);});
 it('surfaces failure and can recover with a later save',async()=>{let broken=true;const error=vi.fn();const q=createSaveQueue(async()=>{if(broken)throw new Error('disk');},error);q.schedule(1);await expect(q.flush()).rejects.toThrow('disk');expect(error).toHaveBeenCalledOnce();broken=false;q.schedule(2);await expect(q.flush()).resolves.toBeUndefined();});
});
