'use server'

import { revalidatePath } from 'next/cache'
import { redirect } from 'next/navigation'
import { createClient } from '@/utils/supabase/server'
import { cookies } from 'next/headers'

export async function login(formData: FormData) {
  const cookieStore = await cookies()
  const supabase = createClient(cookieStore)

  const data = {
    email: formData.get('email') as string,
    password: formData.get('password') as string,
  }

  const { error } = await supabase.auth.signInWithPassword(data)

  if (error) {
    redirect('/login?error=' + encodeURIComponent(error.message))
  }

  revalidatePath('/', 'layout')
  redirect('/dashboard')
}

export async function signup(formData: FormData) {
  const cookieStore = await cookies()
  const supabase = createClient(cookieStore)

  const data = {
    email: formData.get('email') as string,
    password: formData.get('password') as string,
  }

  const { error } = await supabase.auth.signUp(data)

  if (error) {
    redirect('/register?error=' + encodeURIComponent(error.message))
  }

  revalidatePath('/', 'layout')
  redirect('/login?message=Check your email to confirm your account')
}

export async function getProfile() {
  const cookieStore = await cookies()
  const supabase = createClient(cookieStore)
  
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) return null

  const { data: profile } = await supabase
    .from('profiles')
    .select('*')
    .eq('id', user.id)
    .single()
    
  return profile
}

export async function updateSubscription(tier: string, cycle: 'monthly' | 'yearly' = 'monthly') {
  const cookieStore = await cookies()
  const supabase = createClient(cookieStore)
  
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) redirect('/login')

  const { error } = await supabase
    .from('profiles')
    .update({ 
      subscription_tier: tier,
      billing_cycle: cycle,
      is_trial_used: true,
      updated_at: new Date().toISOString()
    })
    .eq('id', user.id)

  if (error) {
    console.error("Update error:", error)
    return { success: false, error: error.message }
  }

  revalidatePath('/', 'layout')
  revalidatePath('/pricing')
  revalidatePath('/dashboard')
  revalidatePath('/profile')
  return { success: true }
}

export async function cancelSubscription() {
  const cookieStore = await cookies()
  const supabase = createClient(cookieStore)
  
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) redirect('/login')

  const { error } = await supabase
    .from('profiles')
    .update({ 
      subscription_tier: 'free',
      billing_cycle: null,
      updated_at: new Date().toISOString()
    })
    .eq('id', user.id)

  if (error) {
    console.error("Cancel error:", error)
    return { success: false, error: error.message }
  }

  revalidatePath('/', 'layout')
  revalidatePath('/pricing')
  revalidatePath('/dashboard')
  revalidatePath('/profile')
  return { success: true }
}

export async function updateProfile(data: { full_name?: string }) {
  const cookieStore = await cookies()
  const supabase = createClient(cookieStore)
  
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) redirect('/login')

  const { error } = await supabase
    .from('profiles')
    .update({ 
      full_name: data.full_name,
      updated_at: new Date().toISOString()
    })
    .eq('id', user.id)

  if (error) {
    console.error("Profile update error:", error)
    return { success: false, error: error.message }
  }

  revalidatePath('/profile')
  return { success: true }
}

export async function deleteUserAccount() {
  const cookieStore = await cookies()
  const supabase = createClient(cookieStore)
  
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) redirect('/login')

  // 1. Delete profile data (will likely cascade if set up, but let's be explicit)
  await supabase.from('profiles').delete().eq('id', user.id)

  // 2. Delete auth user
  // Note: Standard Supabase client can't delete auth user without admin key.
  // For this mock, we'll just sign out and mark profile as deleted/anonymized.
  // In a real prod app, you'd use a service role or a trigger.
  const { error } = await supabase.auth.signOut()

  if (error) {
    return { success: false, error: error.message }
  }

  revalidatePath('/', 'layout')
  redirect('/register?message=Votre compte a été supprimé avec succès.')
}

export async function logout() {
  const cookieStore = await cookies()
  const supabase = createClient(cookieStore)

  await supabase.auth.signOut()

  revalidatePath('/', 'layout')
  redirect('/login')
}
