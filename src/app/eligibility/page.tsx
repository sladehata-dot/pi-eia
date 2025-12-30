'use client';

import { useState } from 'react';
import { createClient } from '@supabase/supabase-js';

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
);

export default function EligibilityPage() {
  const [form, setForm] = useState<any>({});
  const [submitted, setSubmitted] = useState(false);

  const eligible =
    form.homeowner === true &&
    form.property_type === 'house' &&
    (!form.has_solar || form.solar_age_years >= 5);

  const submit = async () => {
    await supabase.from('leads').insert({
      homeowner: form.homeowner,
      property_type: form.property_type,
      has_solar: form.has_solar,
      solar_age_years: form.solar_age_years,
      residents: form.residents,
      residents_changing: form.residents_changing,
      has_ev: form.has_ev,
      ev_timeline: form.ev_timeline,
      likely_to_sell: form.likely_to_sell,
      full_name: form.full_name,
      email: form.email,
      phone: form.phone,
      eligible
    });

    setSubmitted(true);
  };

  if (submitted) {
    return (
      <div style={{ padding: 40 }}>
        <h2>{eligible ? 'You may be eligible 🎉' : 'Thanks for registering'}</h2>
        <p>
          {eligible
            ? 'Next step: upload your energy bills.'
            : 'We’ll keep you informed of future Pi offerings.'}
        </p>
      </div>
    );
  }

  return (
    <div style={{ padding: 40, maxWidth: 600 }}>
      <h1>Eligibility Check</h1>

      <label>
        Homeowner?
        <select onChange={e => setForm({ ...form, homeowner: e.target.value === 'yes' })}>
          <option></option>
          <option value="yes">Yes</option>
          <option value="no">No</option>
        </select>
      </label>

      <br /><br />

      <label>
        Property type
        <select onChange={e => setForm({ ...form, property_type: e.target.value })}>
          <option></option>
          <option value="house">House</option>
          <option value="duplex">Duplex</option>
          <option value="unit">Unit</option>
          <option value="highrise">High-rise</option>
        </select>
      </label>

      <br /><br />

      <label>
        Existing solar?
        <select onChange={e => setForm({ ...form, has_solar: e.target.value === 'yes' })}>
          <option></option>
          <option value="yes">Yes</option>
          <option value="no">No</option>
        </select>
      </label>

      <br /><br />

      {form.has_solar && (
        <>
          <label>
            Solar age (years)
            <input
              type="number"
              onChange={e =>
                setForm({ ...form, solar_age_years: Number(e.target.value) })
              }
            />
          </label>
          <br /><br />
        </>
      )}

      <label>
        Full name
        <input onChange={e => setForm({ ...form, full_name: e.target.value })} />
      </label>

      <br /><br />

      <label>
        Email
        <input onChange={e => setForm({ ...form, email: e.target.value })} />
      </label>

      <br /><br />

      <label>
        Phone
        <input onChange={e => setForm({ ...form, phone: e.target.value })} />
      </label>

      <br /><br />

      <button onClick={submit}>Continue</button>
    </div>
  );
}
