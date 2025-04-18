"use strict";
var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.AppModule = void 0;
const common_1 = require("@nestjs/common");
const prisma_service_1 = require("./prisma.service");
const role_controller_1 = require("./users/role.controller");
const role_service_1 = require("./users/role.service");
const users_module_1 = require("./users/users.module");
const auth_module_1 = require("./auth/auth.module");
const locations_module_1 = require("./users/locations.module");
const last_seen_module_1 = require("./last-seen/last-seen.module");
let AppModule = class AppModule {
};
exports.AppModule = AppModule;
exports.AppModule = AppModule = __decorate([
    (0, common_1.Module)({
        imports: [
            users_module_1.UsersModule,
            auth_module_1.AuthModule,
            locations_module_1.LocationsModule,
            last_seen_module_1.LastSeenModule,
        ],
        controllers: [role_controller_1.RoleController],
        providers: [role_service_1.RoleService, prisma_service_1.PrismaService],
        exports: [role_service_1.RoleService],
    })
], AppModule);
//# sourceMappingURL=app.module.js.map