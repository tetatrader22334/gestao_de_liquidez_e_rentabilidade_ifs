# Relatório SHAP — LSTM AutoML NIM

## Configuração
- Base: `bases/base_final_winsorizada.xlsx`
- Modelo: `outputs/modelos/AM2 - LSTM/geral/NIM/lstm_automl_NIM.keras`
- Preprocessadores: `outputs/modelos/AM2 - LSTM/geral/NIM/preprocessadores_NIM.joblib`
- Target: `NIM`
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
    1 resultado_de_intermediacao_financeira_sobre_ativo_total                0.003367                        0.002335                -0.000645
    2                                       pib_indice_sa_log                0.003179                        0.001339                 0.000946
    3                despesas_de_intermediacao_sobre_receitas                0.003012                        0.002394                -0.001272
    4       rendas_de_prestacao_de_servicos_sobre_ativo_total                0.002970                        0.001590                -0.000206
    5                     despesas_de_captacao_sobre_receitas                0.002945                        0.002344                -0.001380
    6                    operacoes_de_credito_sobre_captacoes                0.002806                        0.002021                -0.000129
    7  receitas_de_intermediacao_financeira_sobre_ativo_total                0.002471                        0.001814                -0.000179
    8           rendas_de_operacoes_com_TVM_sobre_ativo_total                0.002430                        0.001832                 0.000008
    9           resultado_de_provisao_pcddl_sobre_ativo_total                0.002267                        0.001083                -0.000030
   10                             despesas_adm_sobre_receitas                0.002087                        0.001965                -0.001374
   11                                         hhi_periodo_dec                0.001885                        0.001445                -0.001424
   12                     despesas_tributarias_sobre_receitas                0.001749                        0.001280                -0.000894
   13           rendas_de_tarifas_bancarias_sobre_ativo_total                0.001742                        0.001158                -0.000404
   14                   resultado_de_intermediacao_financeira                0.001732                        0.000934                -0.000592
   15                                  ipca_fim_trimestre_dec                0.001625                        0.000623                 0.000232
```

## Importância por defasagem
```
 rank lag  mean_abs_shap_sum_features  mean_shap_sum_features
    1   t                    0.011889               -0.000662
    2 t-7                    0.008123               -0.002243
    3 t-1                    0.006428               -0.001361
    4 t-6                    0.005029               -0.000562
    5 t-5                    0.004448               -0.000958
    6 t-3                    0.004183               -0.000501
    7 t-2                    0.004088               -0.000833
    8 t-4                    0.003645               -0.000613
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

Tempo total de execução: 144.55 segundos.