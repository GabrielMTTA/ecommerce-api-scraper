# Checklist de Deployment

## Pre-Deployment
- [ ] Todos os testes passando (npm test && pytest)
- [ ] Sem vulnerabilidades criticas (npm audit, bandit)
- [ ] TypeScript sem erros
- [ ] Variaveis de ambiente configuradas
- [ ] Banco de dados migrado
- [ ] Redis operacional
- [ ] SSL/TLS configurado
- [ ] Backups configurados

## Deployment
- [ ] Docker images builtadas
- [ ] docker-compose tested em staging
- [ ] Logs centralizados configurados
- [ ] Monitoring e alertas ativos
- [ ] Rate limiting validado
- [ ] CORS configurado corretamente

## Post-Deployment
- [ ] Health checks passando
- [ ] API respondendo em producao
- [ ] Scrapers coletando dados
- [ ] Social media posts funcionando
- [ ] Alertas monitorando sistema
- [ ] Logs sendo coletados
- [ ] Backup rodando

## Seguranca em Producao
- [ ] HTTPS ativo
- [ ] Headers de seguranca presentes
- [ ] Rate limiting funcional
- [ ] Autenticacao JWT validada
- [ ] Senhas nao em logs
- [ ] Acesso de BD restrito
- [ ] Network policies ativas
