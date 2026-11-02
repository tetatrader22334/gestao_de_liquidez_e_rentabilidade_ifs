# Relatório SHAP — LSTM AutoML ROA

## Configuração
- Base: `bases/base_final_winsorizada.xlsx`
- Modelo: `outputs/modelos/AM2 - LSTM/geral/ROE/lstm_automl_ROE.keras`
- Preprocessadores: `outputs/modelos/AM2 - LSTM/geral/ROE/preprocessadores_ROE.joblib`
- Target: `ROE`
- Instituição: `id_entidade`
- Tempo: `AnoMes_ord`
- Horizonte: `1`
- Comprimento da sequência: `8`
- Explainer: `permutation`
- Escala do output: `original do target`

## Amostras
- Dimensão da base: 615 linhas x 82 colunas
- Sequências reconstruídas: 503
- Sequências de background: 40
- Sequências explicadas: 80

## Top 15 variáveis agregadas
```
 rank                                                 feature  mean_abs_shap_sum_lags  mean_abs_of_total_shap_feature  mean_total_shap_feature
    1                                       pib_indice_sa_log                0.014148                        0.008668                 0.008668
    2       rendas_de_prestacao_de_servicos_sobre_ativo_total                0.005877                        0.002255                -0.000545
    3           rendas_de_operacoes_com_TVM_sobre_ativo_total                0.005751                        0.004229                -0.001033
    4                                         hhi_periodo_dec                0.005432                        0.002185                 0.002185
    5  receitas_de_intermediacao_financeira_sobre_ativo_total                0.005219                        0.004119                -0.000499
    6                           multiplicador_capital_proprio                0.003810                        0.003726                 0.002337
    7                   resultado_de_intermediacao_financeira                0.003416                        0.001252                 0.000609
    8           rendas_de_tarifas_bancarias_sobre_ativo_total                0.003055                        0.002359                 0.001558
    9 resultado_de_intermediacao_financeira_sobre_ativo_total                0.003051                        0.001196                 0.000521
   10                                  ipca_fim_trimestre_dec                0.002980                        0.001050                 0.000058
   11           resultado_de_provisao_pcddl_sobre_ativo_total                0.002921                        0.001492                -0.000042
   12                    operacoes_de_credito_sobre_captacoes                0.002367                        0.002095                 0.000032
   13                        disponibilidades_sobre_depositos                0.002264                        0.001345                -0.000823
   14                             despesas_adm_sobre_receitas                0.002071                        0.001964                -0.001235
   15                             captacoes_sobre_ativo_total                0.001920                        0.000629                -0.000253
```

## Importância por defasagem
```
 rank lag  mean_abs_shap_sum_features  mean_shap_sum_features
    1   t                    0.029430                0.007152
    2 t-7                    0.014901               -0.000224
    3 t-1                    0.010807               -0.002233
    4 t-6                    0.006353                0.001453
    5 t-5                    0.004924                0.001126
    6 t-2                    0.004500                0.001303
    7 t-4                    0.004038                0.000943
    8 t-3                    0.003617                0.000635
```

## Arquivos gerados
- `shap_values_flat.npy`
- `shap_values_3d.npy`
- `shap_base_values.npy`
- `metadados_amostras_shap.csv`
- `shap_importance_lag_feature.csv`
- `shap_importance_feature_aggregated.csv`
- `shap_importance_by_lag.csv`
- `shap_bar_flat_top.png`
- `shap_beeswarm_flat_top.png`
- `shap_bar_feature_aggregated_top.png`
- `shap_heatmap_feature_lag_top.png`

Tempo total de execução: 197.60 segundos.