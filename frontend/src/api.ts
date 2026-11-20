const API=import.meta.env.VITE_API_BASE||"";
export type User={id:number;email:string;role:string};
export type Device={device_id:string;name:string;online:boolean;password_expires_at:string};
export async function request<T>(path:string,token?:string,body?:unknown):Promise<T>{
 const response=await fetch(API+path,{method:body?"POST":"GET",headers:{"Content-Type":"application/json",...(token?{Authorization:`Bearer ${token}`}:{})},...(body?{body:JSON.stringify(body)}:{})});
 const data=await response.json();if(!response.ok)throw new Error(data.detail||"Request failed");return data as T;
}
export const wsUrl=(path:string)=>`${location.protocol==="https:"?"wss:":"ws:"}//${location.host}${path}`;
