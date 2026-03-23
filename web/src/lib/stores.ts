import { writable } from 'svelte/store';

export const theme = writable<'dark' | 'light'>('dark');
export const scanning = writable(false);
