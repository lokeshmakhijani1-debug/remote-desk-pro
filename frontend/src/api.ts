const API=import.meta.env.VITE_API_BASE||"";
export type User={id:number;email:string;role:string};
export type Device={device_id:string;name:string;online:boolean;password_expires_at:string};

function formatApiError(detail: unknown): string {
 if (typeof detail === "string" && detail.trim()) return detail;
 if (Array.isArray(detail)) {
  const messages = detail.map((item: unknown) => {
   if (!item || typeof item !== "object") return String(item);
   const error = item as { loc?: unknown; msg?: unknown };
   const location = Array.isArray(error.loc)
    ? error.loc.filter((part): part is string | number => typeof part === "string" || typeof part === "number").filter(part => part !== "body").join(".")
    : "";
   const message = typeof error.msg === "string" ? error.msg : "Invalid value";
   return location ? `${location}: ${message}` : message;
  }).filter(Boolean);
  if (messages.length) return messages.join("; ");
 }
 if (detail && typeof detail === "object") {
  const error = detail as { msg?: unknown; message?: unknown };
  if (typeof error.msg === "string") return error.msg;
  if (typeof error.message === "string") return error.message;
  try { return JSON.stringify(detail); } catch { /* fall through */ }
 }
 return "Request failed. Please check your details and try again.";
}

export async function request<T>(path:string,token?:string,body?:unknown):Promise<T>{
 const response=await fetch(API+path,{method:body? "POST":"GET",headers:{"Content-Type":"application/json",...(token?{Authorization:`Bearer ${token}`}:{})},...(body?{body:JSON.stringify(body)}:{})});
 let data: {detail?: unknown} & Record<string, unknown>;
 try { data = await response.json(); }
 catch { throw new Error(response.ok ? "The server returned an unreadable response." : `Request failed (HTTP ${response.status}).`); }
 if(!response.ok) throw new Error(formatApiError(data.detail) || `Request failed (HTTP ${response.status}).`);
 return data as T;
}
export const wsUrl=(path:string)=>`${location.protocol==="https:"?"wss:":"ws:"}//${location.host}${path}`;
