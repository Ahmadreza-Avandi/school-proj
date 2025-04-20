// src/prisma.service.ts
import { Injectable, OnModuleInit, OnModuleDestroy, Logger } from '@nestjs/common';
import { PrismaClient } from '@prisma/client';

@Injectable()
export class PrismaService extends PrismaClient implements OnModuleInit, OnModuleDestroy {
  private readonly logger = new Logger(PrismaService.name);

  constructor() {
    super({
      log: [
        { emit: 'event', level: 'query' },
        { emit: 'event', level: 'error' },
        { emit: 'event', level: 'info' },
        { emit: 'event', level: 'warn' },
      ],
    });
  }

  async onModuleInit() {
    try {
      this.logger.log('Connecting to database...');
      await this.$connect();
      this.logger.log('Database connection established successfully');

      // اضافه کردن لیسنرها برای رخدادهای مختلف
      this.$on('error', (e) => {
        this.logger.error(`Prisma Error: ${e.message}`, e.stack);
      });
      
      this.$on('query', (e) => {
        this.logger.debug(`Prisma Query: ${e.query}`);
      });
      
      this.$on('info', (e) => {
        this.logger.log(`Prisma Info: ${e.message}`);
      });
      
      this.$on('warn', (e) => {
        this.logger.warn(`Prisma Warning: ${e.message}`);
      });

    } catch (error) {
      this.logger.error(`Failed to connect to the database: ${error.message}`, error.stack);
      throw error;
    }
  }

  async onModuleDestroy() {
    this.logger.log('Disconnecting from database...');
    await this.$disconnect();
    this.logger.log('Database connection closed');
  }
}
