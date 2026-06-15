using asset.intel as intel from '../db/schema';
service AssetService @(path:'/asset') {
  @readonly entity Assets             as projection on intel.Assets;
  @readonly entity SensorReadings     as projection on intel.SensorReadings;
           entity WorkOrders          as projection on intel.WorkOrders;
  @readonly entity FailureHistory     as projection on intel.FailureHistory;
  @readonly entity ProcessTrends      as projection on intel.ProcessTrends;
  @readonly entity ComplianceDocs     as projection on intel.ComplianceDocs;
  @readonly entity Inspections        as projection on intel.Inspections;
  @readonly entity AssetHealthScores  as projection on intel.AssetHealthScores;
  @readonly entity HealthScores       as projection on intel.AssetHealthScores;
  @readonly entity Thresholds         as projection on intel.AssetThresholds;
  @readonly entity Financials         as projection on intel.AssetFinancials;

  action askAI(question: String) returns { answer: String };
}
