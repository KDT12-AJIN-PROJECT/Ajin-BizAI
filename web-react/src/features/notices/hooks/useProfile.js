import { useEffect, useState } from 'react'
import { profileApi } from '../../../api/backendApi'
import { DEFAULT_PROFILE_DATA } from '../../../config/defaults'

/** DB row(snake_case) → React profileData(camelCase) */
function dbToProfile(row) {
  return {
    companyName:    row.company_name    ?? DEFAULT_PROFILE_DATA.companyName,
    representative: row.representative  ?? DEFAULT_PROFILE_DATA.representative,
    bizNumber:      row.biz_number      ?? DEFAULT_PROFILE_DATA.bizNumber,
    foundedDate:    row.founded_date    ?? DEFAULT_PROFILE_DATA.foundedDate,
    region:         row.region          ?? DEFAULT_PROFILE_DATA.region,
    address:        row.address         ?? DEFAULT_PROFILE_DATA.address,
    industry:       row.industry        ?? DEFAULT_PROFILE_DATA.industry,
    subIndustry:    row.sub_industry    ?? DEFAULT_PROFILE_DATA.subIndustry,
    employees:      row.employees       ?? DEFAULT_PROFILE_DATA.employees,
    revenueRange:   row.revenue_range   ?? DEFAULT_PROFILE_DATA.revenueRange,
    certifications: row.certifications  ?? DEFAULT_PROFILE_DATA.certifications,
    matchKeywords:  row.match_keywords  ?? DEFAULT_PROFILE_DATA.matchKeywords,
    excludeKeywords:row.exclude_keywords?? DEFAULT_PROFILE_DATA.excludeKeywords,
    sales:          row.sales           ?? DEFAULT_PROFILE_DATA.sales,
    field:          row.field           ?? DEFAULT_PROFILE_DATA.field,
    summary:        row.summary         ?? DEFAULT_PROFILE_DATA.summary,
    strategy:       row.strategy        ?? DEFAULT_PROFILE_DATA.strategy,
    achievements:   row.achievements    ?? DEFAULT_PROFILE_DATA.achievements,
    coreTech:       row.core_tech       ?? DEFAULT_PROFILE_DATA.coreTech,
    coreTeam:       row.core_team       ?? DEFAULT_PROFILE_DATA.coreTeam,
  }
}

/** React profileData(camelCase) → API body(snake_case) */
function profileToDb(p) {
  return {
    company_name:    p.companyName,
    representative:  p.representative,
    biz_number:      p.bizNumber,
    founded_date:    p.foundedDate,
    region:          p.region,
    address:         p.address,
    industry:        p.industry,
    sub_industry:    p.subIndustry,
    employees:       p.employees,
    revenue_range:   p.revenueRange,
    certifications:  p.certifications,
    match_keywords:  p.matchKeywords,
    exclude_keywords:p.excludeKeywords,
    sales:           p.sales,
    field:           p.field,
    summary:         p.summary,
    strategy:        p.strategy,
    achievements:    p.achievements,
    core_tech:       p.coreTech,
    core_team:       p.coreTeam,
  }
}

export function useProfile() {
  const [profileData, setProfileData] = useState(DEFAULT_PROFILE_DATA)
  const [loaded, setLoaded] = useState(false)

  // 앱 시작 시 DB에서 프로필 로드
  useEffect(() => {
    profileApi.get()
      .then((row) => {
        setProfileData(dbToProfile(row))
      })
      .catch(() => {/* 백엔드 없으면 기본값 유지 */})
      .finally(() => setLoaded(true))
  }, [])

  // 저장: DB에 upsert
  const saveProfile = async (data) => {
    try {
      const row = await profileApi.save(profileToDb(data))
      setProfileData(dbToProfile(row))
    } catch {
      // 백엔드 실패해도 로컬 상태는 유지
      setProfileData(data)
    }
  }

  return { profileData, setProfileData, saveProfile, loaded }
}
