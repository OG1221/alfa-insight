export async function api<T>(path:string,options:RequestInit={}):Promise<T>{
 const token=sessionStorage.getItem('alfa-token');
 const headers:Record<string,string>={'Content-Type':'application/json',...(token?{Authorization:`Bearer ${token}`}:{})};
 if(options.body instanceof FormData)delete headers['Content-Type'];
 const response=await fetch('/api'+path,{...options,headers:{...headers,...options.headers}});
 if(!response.ok){const body=await response.json().catch(()=>({detail:'Сервис временно недоступен'}));throw new Error(typeof body.detail==='string'?body.detail:'Проверьте заполнение полей');}
 return response.json();
}
