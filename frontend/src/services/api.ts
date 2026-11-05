import axios from 'axios';
export const api=axios.create({baseURL:import.meta.env.VITE_API_URL || '/api',timeout:30000,withCredentials:true});
export function errorMessage(error:unknown):string {if(axios.isAxiosError(error)){const detail=error.response?.data?.detail;return typeof detail==='string'?detail:error.response?.status===422?'Check the quantity, price, symbol and date.':'Unable to connect. Make sure the local backend is running.';}return 'Something went wrong. Please try again.';}
