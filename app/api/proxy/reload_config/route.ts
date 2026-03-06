import { NextResponse } from 'next/server';

export async function POST() {
  try {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';
    
    const response = await fetch(`${apiUrl}/api/reload_config`, {
      method: 'POST',
    });
    
    const data = await response.json();
    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    console.error('Erro no proxy reload_config:', error);
    return NextResponse.json({ error: 'Falha ao conectar com o backend' }, { status: 500 });
  }
}
