export interface ActiveTransfer {
 transfer_id:string;name:string;total_size:number;sha256:string;chunk_size:number;compression:"none"|"zstd";ackedOffset:number;file:Blob;updatedAt:number;
}
const DB="remote-desk-pro-transfers",STORE="active";
function openDb():Promise<IDBDatabase>{return new Promise((resolve,reject)=>{try{const request=indexedDB.open(DB,1);request.onupgradeneeded=()=>{if(!request.result.objectStoreNames.contains(STORE))request.result.createObjectStore(STORE,{keyPath:"transfer_id"});};request.onsuccess=()=>resolve(request.result);request.onerror=()=>reject(request.error??new Error("IndexedDB open failed"));request.onblocked=()=>reject(new Error("IndexedDB upgrade blocked"));}catch(error){reject(error);}});}
async function request<T>(mode:IDBTransactionMode,operation:(store:IDBObjectStore)=>IDBRequest<T>):Promise<T>{const db=await openDb();try{return await new Promise<T>((resolve,reject)=>{const tx=db.transaction(STORE,mode),req=operation(tx.objectStore(STORE));req.onsuccess=()=>resolve(req.result);req.onerror=()=>reject(req.error??new Error("IndexedDB request failed"));tx.onabort=()=>reject(tx.error??new Error("IndexedDB transaction aborted"));});}finally{db.close();}}
export function saveTransfer(value:ActiveTransfer):Promise<IDBValidKey>{return request("readwrite",store=>store.put({...value,updatedAt:Date.now()}));}
export function loadTransfer():Promise<ActiveTransfer|undefined>{return request<ActiveTransfer[]>("readonly",store=>store.getAll()).then(values=>values.sort((a,b)=>b.updatedAt-a.updatedAt)[0]);}
export function deleteTransfer(id:string):Promise<undefined>{return request("readwrite",store=>store.delete(id)).then(()=>undefined);}
